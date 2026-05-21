from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from tests.evals.common import build_run_manifest, default_scoring_config_payload, finalize_run_manifest, stable_payload_hash
from tests.evals.personamem_v2.analysis import analyze_personamem_evidence
from tests.evals.personamem_v2.candidate_views import (
    PERSONA_ID,
    CandidateView,
    extract_candidate_views,
)
from tests.evals.personamem_v2.candidate_view_writer import (
    CandidateViewWriter,
    CandidateViewWriteResult,
    CandidateViewWritePolicy,
)
from tests.evals.personamem_v2.candidate_view_reporting import save_candidate_detailed_report
from tests.evals.personamem_v2.loader import (
    DEFAULT_SPLIT,
    PERSONAMEM_CACHE_DIR,
    build_samples,
    load_personamem_rows,
    save_rows_snapshot,
    snippet_to_turns,
)
from tests.evals.personamem_v2.models import EvalMode, PersonaMemQuestion, PersonaMemReport, PersonaMemSample
from tests.evals.personamem_v2.runner import (
    _reset_user_memory,
    ensure_user_onboarded,
    evaluate_sample,
    resolve_existing_user,
)
from tests.evals.personamem_v2.reporting import build_paired_comparison

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("test_results") / "personamem_v2_candidate_experiment"
EXPERIMENT_PERSONA_ID = f"{PERSONA_ID}_candidate_views"
EXPERIMENT_USER_KEY = f"personamem_v2_persona_{EXPERIMENT_PERSONA_ID}"
WRITE_WINDOW_TURNS = 5
WRITEABLE_VIEW_TYPES = {
    "user_fact",
    "episodic_event",
    "artifact_fact",
    "constraint",
    "surviving_need",
}


@dataclass(frozen=True)
class PlannedCandidateTurn:
    """One original conversation turn plus the candidate set observed for its row."""

    row_index: int
    turn_index: int
    user_input: str
    assistant_response: str
    candidates: list[dict[str, Any]]


def build_candidate_turn_plan(question: PersonaMemQuestion) -> list[PlannedCandidateTurn]:
    """Group original turns into write windows and attach candidates as structured trace only."""
    candidates = []
    for candidate in extract_candidate_views(question):
        item = candidate.to_dict()
        item["writable"] = _should_project_candidate(candidate)
        candidates.append(item)

    turns = snippet_to_turns(question)
    planned_turns: list[PlannedCandidateTurn] = []
    for window_index, start in enumerate(range(0, len(turns), WRITE_WINDOW_TURNS), start=1):
        window = turns[start : start + WRITE_WINDOW_TURNS]
        planned_turns.append(
            PlannedCandidateTurn(
                row_index=question.row_index,
                turn_index=window_index,
                user_input="\n".join(user_input for user_input, _ in window if user_input),
                assistant_response="\n".join(
                    assistant_response for _, assistant_response in window if assistant_response
                ),
                candidates=candidates,
            )
        )
    return planned_turns


def clone_sample_for_candidate_experiment(sample: PersonaMemSample) -> PersonaMemSample:
    """Use a separate DB user while keeping the evaluated questions from persona 66."""
    return replace(
        sample,
        persona_id=EXPERIMENT_PERSONA_ID,
        user_key=EXPERIMENT_USER_KEY,
    )


def validate_candidate_sample_isolation(sample: PersonaMemSample) -> None:
    if sample.persona_id != EXPERIMENT_PERSONA_ID or sample.user_key != EXPERIMENT_USER_KEY:
        raise ValueError(
            "Candidate projection imports must use the isolated candidate user: "
            f"persona_id={EXPERIMENT_PERSONA_ID} user_key={EXPERIMENT_USER_KEY}."
        )


def filter_sample_by_row_indexes(
    sample: PersonaMemSample,
    row_indexes: list[int] | None,
) -> PersonaMemSample:
    if not row_indexes:
        return sample
    target_rows = {int(row_index) for row_index in row_indexes}
    return replace(
        sample,
        questions=[question for question in sample.questions if question.row_index in target_rows],
    )


async def import_candidate_view_sample(
    session: AsyncSession,
    sample: PersonaMemSample,
    *,
    enable_dedup: bool = False,
    reset_memory: bool = False,
) -> tuple[str, int, list[dict[str, Any]]]:
    validate_candidate_sample_isolation(sample)
    user_id = await ensure_user_onboarded(
        session,
        sample,
        recreate_existing=reset_memory,
    )
    if reset_memory:
        await _reset_user_memory(session, user_id)

    llm = LLMFactory.get_provider()
    writer = CandidateViewWriter(session=session, llm=llm)
    memory_count = 0
    candidate_write_trace: list[dict[str, Any]] = []

    for question in sample.questions:
        for planned in build_candidate_turn_plan(question):
            try:
                write_result = await writer.write_turn(user_id=user_id, planned_turn=planned)
                memory_count += 1
                candidate_write_trace.append(_candidate_write_trace_item(write_result))
                if memory_count % 10 == 0:
                    await session.commit()
            except Exception as exc:
                await session.rollback()
                raise RuntimeError(
                    "Candidate projection write failed: "
                    f"row_index={question.row_index} turn_index={planned.turn_index}"
                ) from exc

    await session.commit()
    return user_id, memory_count, candidate_write_trace


async def run_candidate_view_trace_experiment(
    *,
    split: str = DEFAULT_SPLIT,
    max_questions: int | None = None,
    max_rows: int | None = None,
    eval_mode: EvalMode = EvalMode.STORAGE,
    top_k: int = 10,
    row_indexes: list[int] | None = None,
    baseline_results_path: Path | None = None,
    reuse_candidate_user: bool = False,
    enable_dedup: bool = False,
    reset_memory: bool = True,
    save_raw_snapshot: bool = False,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    if baseline_results_path is None:
        raise ValueError(
            "baseline_results_path is required so candidate experiments do not import or reset "
            f"the official personamem_v2_persona_{PERSONA_ID} DB user."
        )

    rows = load_personamem_rows(
        split=split,
        max_rows=max_rows,
        cache_dir=PERSONAMEM_CACHE_DIR,
    )
    dataset_hash = stable_payload_hash(rows)
    if save_raw_snapshot:
        save_rows_snapshot(rows, split=split, output_dir=output_dir / "raw_snapshots")
    samples = build_samples(
        rows,
        split=split,
        persona_id=PERSONA_ID,
        max_questions=max_questions,
    )
    if not samples:
        raise RuntimeError(f"No PersonaMem-v2 rows found for persona_id={PERSONA_ID}.")

    sample = filter_sample_by_row_indexes(samples[0], row_indexes)
    if not sample.questions:
        raise RuntimeError(f"No persona {PERSONA_ID} questions matched row indexes: {row_indexes}.")
    candidate_sample = clone_sample_for_candidate_experiment(sample)

    async with AsyncSessionLocal() as session:
        logger.info("Loading baseline summary from %s", baseline_results_path)
        baseline_summary = load_baseline_summary(baseline_results_path, row_indexes=row_indexes)
        validate_baseline_summary(baseline_summary, sample)

        logger.info(
            "Running candidate-view structured projection/eval: persona_id=%s original_turn_count=%s mode=%s",
            EXPERIMENT_PERSONA_ID,
            summarize_candidate_projection(sample)["original_turn_count"],
            eval_mode.value,
        )
        if reuse_candidate_user:
            resolved = await resolve_existing_user(session, candidate_sample)
            if not resolved:
                raise RuntimeError(
                    f"Candidate-view user does not exist: {candidate_sample.user_key}. "
                    "Run storage import first before using reuse mode."
                )
            candidate_user_id, candidate_memory_count = resolved
            candidate_write_trace = []
            logger.info(
                "Reusing existing candidate-view user: user_id=%s resources=%s",
                candidate_user_id,
                candidate_memory_count,
            )
        else:
            candidate_user_id, candidate_memory_count, candidate_write_trace = await import_candidate_view_sample(
                session=session,
                sample=candidate_sample,
                enable_dedup=enable_dedup,
                reset_memory=reset_memory,
            )
        candidate_report = await evaluate_sample(
            session=session,
            sample=sample,
            user_id=candidate_user_id,
            memory_count=candidate_memory_count,
            sample_index=1,
            eval_mode=eval_mode,
            top_k=top_k,
        )

    candidate_summary = summarize_personamem_report(candidate_report)
    if reuse_candidate_user:
        candidate_summary = make_reused_candidate_summary(
            candidate_report,
            resource_count=candidate_summary["metrics"]["total_memories"],
        )
    test_info = {
        "dataset": "bowen-upenn/PersonaMem-v2",
        "harness": "personamem_v2_candidate_view_structured_projection",
        "persona_id": PERSONA_ID,
        "experiment_user_persona_id": EXPERIMENT_PERSONA_ID,
        "eval_mode": eval_mode.value,
        "top_k": top_k,
        "baseline_results_path": str(baseline_results_path),
        "projection_mode": "candidate_structured_db_writes",
    }
    run_manifest = build_run_manifest(
        harness="personamem_v2_candidate_view_structured_projection",
        eval_mode=eval_mode.value,
        dataset="bowen-upenn/PersonaMem-v2",
        split=split,
        persona_id=PERSONA_ID,
        question_count=sample.total_questions,
        import_only=False,
        retrieval_only=reuse_candidate_user,
        reset_memory=reset_memory,
        chat_model=candidate_report.chat_model,
        evaluator_model=candidate_report.evaluator_model,
        evaluator_isolated=candidate_report.evaluator_isolated,
        top_k=top_k,
        scoring_config=default_scoring_config_payload(),
        rerank_config=None,
        dataset_hash=dataset_hash,
        cache_hash=stable_payload_hash({"baseline": str(baseline_results_path), "rows": row_indexes}),
        temperature=0.7,
        extra={
            "experiment_user_persona_id": EXPERIMENT_PERSONA_ID,
            "baseline_results_path": str(baseline_results_path),
            "projection_mode": "candidate_structured_db_writes",
        },
    )
    detailed_results_path, detailed_analysis_path = save_candidate_detailed_report(
        candidate_report,
        output_dir / f"persona_{PERSONA_ID}_candidate_view_projection_{eval_mode.value}_results.json",
        eval_mode=eval_mode.value,
        test_info=test_info,
        run_manifest=run_manifest,
    )
    report = {
        "test_info": test_info,
        "run_manifest": run_manifest,
        "baseline": baseline_summary,
        "candidate_structured_projection": candidate_summary,
        "delta": summarize_report_delta(baseline_summary, candidate_summary),
        "paired_comparison": build_candidate_paired_comparison(baseline_summary, candidate_summary),
        "candidate_projection": summarize_candidate_projection(sample),
        "candidate_write_trace": candidate_write_trace,
        "candidate_analysis": {
            "results_json_path": str(detailed_results_path),
            "analysis_markdown_path": str(detailed_analysis_path),
        },
    }
    json_path, markdown_path = save_candidate_experiment_report(report, output_dir)
    report["paths"] = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    return report


def summarize_candidate_projection(sample: PersonaMemSample) -> dict[str, Any]:
    original_turn_count = 0
    candidate_count = 0
    written_candidate_count = 0
    skipped_candidate_count = 0
    written_by_type: dict[str, int] = {}
    skipped_by_reason: dict[str, int] = {}
    policy = CandidateViewWritePolicy()
    for question in sample.questions:
        planned_turns = build_candidate_turn_plan(question)
        original_turn_count += len(planned_turns)
        if not planned_turns:
            continue
        projections = policy.project_candidates(
            row_index=question.row_index,
            turn_index=1,
            candidates=planned_turns[0].candidates,
        )
        candidate_count += len(projections)
        for projection in projections:
            if projection.write_decision == "written":
                written_candidate_count += 1
                written_by_type[projection.view_type] = written_by_type.get(projection.view_type, 0) + 1
            else:
                skipped_candidate_count += 1
                skipped_by_reason[projection.skip_reason] = skipped_by_reason.get(projection.skip_reason, 0) + 1
    return {
        "original_turn_count": original_turn_count,
        "candidate_count": candidate_count,
        "written_candidate_count": written_candidate_count,
        "skipped_candidate_count": skipped_candidate_count,
        "written_by_type": dict(sorted(written_by_type.items())),
        "skipped_by_reason": dict(sorted(skipped_by_reason.items())),
    }


def load_baseline_summary(
    path: Path,
    *,
    row_indexes: list[int] | None = None,
) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "analyses" in data:
        return _summary_from_storage_quality_json(data, row_indexes=row_indexes)
    return _summary_from_standard_results_json(data, row_indexes=row_indexes)


def validate_baseline_summary(
    baseline_summary: dict[str, Any],
    sample: PersonaMemSample,
) -> None:
    baseline_questions = int(baseline_summary.get("metrics", {}).get("total_questions") or 0)
    if baseline_questions != sample.total_questions:
        raise ValueError(
            "Baseline question count mismatch: "
            f"baseline={baseline_questions} sample={sample.total_questions}"
        )
    baseline_persona = str(baseline_summary.get("sample", {}).get("persona_id") or "")
    if baseline_persona and baseline_persona != PERSONA_ID:
        raise ValueError(
            f"Baseline persona mismatch: baseline={baseline_persona} expected={PERSONA_ID}"
        )


def _summary_from_standard_results_json(
    data: dict[str, Any],
    *,
    row_indexes: list[int] | None,
) -> dict[str, Any]:
    target_rows = {int(row_index) for row_index in row_indexes or []}
    rows = [
        qa
        for sample in data.get("samples", [])
        for qa in sample.get("qa_results", [])
        if not target_rows or int(qa.get("row_index", -1)) in target_rows
    ]
    forget_rows = [row for row in rows if _is_forget_question(row.get("supporting_preference", ""))]
    non_forget_rows = [row for row in rows if not _is_forget_question(row.get("supporting_preference", ""))]
    first_sample = (data.get("samples") or [{}])[0]
    return {
        "metrics": {
            "total_questions": len(rows),
            "total_memories": int(first_sample.get("total_memories") or 0),
            "storage_hits": sum(1 for row in rows if row.get("storage_hit")),
            "non_forget_storage_hits": sum(1 for row in non_forget_rows if row.get("storage_hit")),
            "forget_total": len(forget_rows),
            "forget_safe": sum(1 for row in forget_rows if row.get("storage_hit") is False),
            "retrieval_hits": sum(1 for row in rows if row.get("retrieval_hit")),
            "correct_answers": sum(1 for row in rows if row.get("is_correct")),
            "errors": sum(1 for row in rows if row.get("error")),
        },
        "sample": {
            "persona_id": first_sample.get("persona_id", PERSONA_ID),
            "user_id": first_sample.get("user_id", ""),
            "total_sessions": first_sample.get("total_sessions", len(rows)),
        },
        "rows": [
            {
                "row_index": row.get("row_index"),
                "storage_hit": row.get("storage_hit"),
                "retrieval_hit": row.get("retrieval_hit"),
                "is_correct": row.get("is_correct"),
                "question": row.get("question"),
                "standard_answer": row.get("standard_answer") or row.get("correct_answer"),
                "supporting_preference": row.get("supporting_preference") or row.get("preference"),
                "retrieval_stage": row.get("retrieval_stage"),
                "rank_position": row.get("rank_position"),
                "error": row.get("error"),
            }
            for row in rows
        ],
    }


def _summary_from_storage_quality_json(
    data: dict[str, Any],
    *,
    row_indexes: list[int] | None,
) -> dict[str, Any]:
    target_rows = {int(row_index) for row_index in row_indexes or []}
    rows = [
        item
        for item in data.get("analyses", [])
        if not target_rows or int(item.get("row_index", -1)) in target_rows
    ]
    forget_rows = [row for row in rows if _is_forget_question(row.get("supporting_preference", ""))]
    non_forget_rows = [row for row in rows if not _is_forget_question(row.get("supporting_preference", ""))]
    return {
        "metrics": {
            "total_questions": len(rows),
            "total_memories": int(data.get("resource_count") or 0),
            "storage_hits": sum(1 for row in rows if row.get("sufficient")),
            "non_forget_storage_hits": sum(1 for row in non_forget_rows if row.get("sufficient")),
            "forget_total": len(forget_rows),
            "forget_safe": sum(
                1
                for row in forget_rows
                if not row.get("sufficient") and not row.get("partial") and not row.get("exact_match")
            ),
            "retrieval_hits": 0,
            "correct_answers": sum(1 for row in rows if row.get("sufficient")),
            "errors": 0,
        },
        "sample": {
            "persona_id": data.get("persona_id", PERSONA_ID),
            "user_id": data.get("username", ""),
            "total_sessions": len(rows),
        },
        "rows": [
            {
                "row_index": row.get("row_index"),
                "storage_hit": bool(row.get("sufficient")),
                "retrieval_hit": None,
                "is_correct": bool(row.get("sufficient")),
                "question": row.get("question"),
                "standard_answer": row.get("correct_answer") or row.get("answer"),
                "supporting_preference": row.get("supporting_preference") or row.get("preference"),
                "retrieval_stage": {
                    "answerable_context_hit": bool(row.get("sufficient")),
                    "target_answer_anchor_hit": bool(row.get("exact_match")),
                    "retrieval_failure_subtype": "none" if row.get("sufficient") else "target_evidence_not_retrieved",
                },
                "rank_position": None,
                "error": None,
            }
            for row in rows
        ],
    }


def summarize_personamem_report(report: PersonaMemReport) -> dict[str, Any]:
    total_questions = report.total_questions
    forget_results = [result for result in report.results if _is_forget_question(result.preference)]
    non_forget_results = [result for result in report.results if not _is_forget_question(result.preference)]
    return {
        "metrics": {
            "total_questions": total_questions,
            "total_memories": report.total_memories,
            "storage_hits": sum(1 for result in report.results if result.storage_hit),
            "non_forget_storage_hits": sum(1 for result in non_forget_results if result.storage_hit),
            "forget_total": len(forget_results),
            "forget_safe": sum(
                1
                for result in forget_results
                if result.storage_hit is False and not result.error
            ),
            "retrieval_hits": sum(1 for result in report.results if result.retrieval_hit),
            "correct_answers": sum(1 for result in report.results if result.is_correct),
            "errors": sum(1 for result in report.results if result.error),
        },
        "sample": {
            "persona_id": report.character,
            "user_id": report.user_id,
            "total_sessions": report.total_sessions,
        },
        "rows": [
            {
                "row_index": result.row_index,
                "storage_hit": result.storage_hit,
                "retrieval_hit": result.retrieval_hit,
                "is_correct": result.is_correct,
                "question": result.question,
                "standard_answer": result.expected_answer,
                "supporting_preference": result.preference,
                "retrieval_stage": analyze_personamem_evidence(
                    question=result.question,
                    correct_answer=result.expected_answer,
                    supporting_preference=result.preference,
                    related_conversation_snippet=result.related_conversation_snippet,
                    incorrect_answers=result.incorrect_answers,
                    contexts=result.retrieved_contexts,
                    scores=result.retrieved_scores,
                    stage="retrieval_top_k",
                    loose_rank_position=result.rank_position,
                    retrieval_hit_loose=result.retrieval_hit,
                ),
                "rank_position": result.rank_position,
                "error": result.error,
            }
            for result in report.results
        ],
    }


def make_reused_candidate_summary(
    report: PersonaMemReport,
    *,
    resource_count: int,
) -> dict[str, Any]:
    summary = summarize_personamem_report(report)
    summary["metrics"]["total_memories"] = resource_count
    summary["sample"]["reused_candidate_user"] = True
    summary["sample"]["provenance_warning"] = (
        "candidate DB state was reused without row-level write trace"
    )
    return summary


def summarize_report_delta(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_metrics = baseline.get("metrics", {})
    candidate_metrics = candidate.get("metrics", {})
    keys = (
        "storage_hits",
        "non_forget_storage_hits",
        "forget_safe",
        "retrieval_hits",
        "correct_answers",
        "total_memories",
        "errors",
    )
    delta = {
        f"{key}_delta": int(candidate_metrics.get(key, 0)) - int(baseline_metrics.get(key, 0))
        for key in keys
    }
    delta["total_questions"] = int(candidate_metrics.get("total_questions") or baseline_metrics.get("total_questions") or 0)
    return delta


def build_candidate_paired_comparison(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_rows = [_candidate_row_for_pair(row) for row in baseline.get("rows", [])]
    candidate_rows = [_candidate_row_for_pair(row) for row in candidate.get("rows", [])]
    paired = build_paired_comparison(baseline_rows, candidate_rows)
    paired["formal_ab_eligible"] = False
    paired["diagnostic_reason"] = (
        "candidate_view_projection_changes_storage_representation; "
        "use answerable evidence and per-row win/loss before promotion"
    )
    return paired


def _candidate_row_for_pair(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "persona_id": PERSONA_ID,
        "source_split": DEFAULT_SPLIT,
        "row_index": row.get("row_index"),
        "question": row.get("question") or f"row_{row.get('row_index')}",
        "standard_answer": row.get("standard_answer"),
        "supporting_preference": row.get("supporting_preference"),
        "is_correct": row.get("is_correct"),
        "retrieval_stage": row.get("retrieval_stage") or {
            "answerable_context_hit": row.get("retrieval_hit") is True or row.get("storage_hit") is True
        },
    }


def save_candidate_experiment_report(report: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = report["test_info"]["eval_mode"]
    json_path = output_dir / f"persona_{PERSONA_ID}_candidate_view_projection_{mode}_comparison.json"
    markdown_path = output_dir / f"persona_{PERSONA_ID}_candidate_view_projection_{mode}_comparison.md"
    finalize_run_manifest(report["run_manifest"], result_file_path=json_path)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_candidate_experiment_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_candidate_experiment_markdown(report: dict[str, Any]) -> str:
    candidate_section = report.get("candidate_structured_projection") or {}
    lines = [
        f"# PersonaMem-v2 Candidate View Structured Projection Comparison - persona {report['test_info']['persona_id']}",
        "",
        f"- eval_mode: {report['test_info']['eval_mode']}",
        f"- top_k: {report['test_info']['top_k']}",
        f"- projection_mode: {report['test_info'].get('projection_mode', 'candidate_structured_db_writes')}",
        "",
        "## Delta",
    ]
    for key, value in report["delta"].items():
        lines.append(f"- {key}: {value}")
    paired = report.get("paired_comparison") or {}
    if paired:
        confidence = (paired.get("statistical_confidence") or {}).get("answer_paired_win_loss") or {}
        lines.extend(
            [
                "",
                "## Per-Row Win/Loss",
                f"- shared_questions: {paired.get('shared_questions')}",
                f"- gain: {paired.get('gain')}",
                f"- regression: {paired.get('regression')}",
                f"- evidence_gain: {paired.get('evidence_gain')}",
                f"- evidence_regression: {paired.get('evidence_regression')}",
                f"- answer_delta_ci95: {confidence.get('normal_approx_ci_95')}",
                f"- formal_ab_eligible: {paired.get('formal_ab_eligible')}",
            ]
        )

    lines.extend(["", "## Baseline"])
    for key, value in report["baseline"]["metrics"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Candidate Structured Projection"])
    for key, value in candidate_section.get("metrics", {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Candidate Projection"])
    projection = report["candidate_projection"]
    lines.append(f"- original_turn_count: {projection['original_turn_count']}")
    lines.append(f"- candidate_count: {projection['candidate_count']}")
    lines.append(f"- written_candidate_count: {projection['written_candidate_count']}")
    lines.append(f"- skipped_candidate_count: {projection['skipped_candidate_count']}")
    for key, value in projection["written_by_type"].items():
        lines.append(f"- written_{key}: {value}")
    for key, value in projection["skipped_by_reason"].items():
        lines.append(f"- skipped_{key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run PersonaMem-v2 candidate-view trace comparison.")
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument(
        "--eval-mode",
        choices=[mode.value for mode in EvalMode],
        default=EvalMode.STORAGE.value,
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--row-index", action="append", type=int, default=None)
    parser.add_argument("--baseline-results-path", type=Path, required=True)
    parser.add_argument("--reuse-candidate-user", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--no-dedup", action="store_true")
    parser.add_argument("--no-reset-memory", action="store_true")
    parser.add_argument("--save-raw-snapshot", action="store_true")
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_candidate_view_trace_experiment(
            split=args.split,
            max_questions=args.max_questions,
            max_rows=args.max_rows,
            eval_mode=EvalMode(args.eval_mode),
            top_k=args.top_k,
            row_indexes=args.row_index,
            baseline_results_path=args.baseline_results_path,
            reuse_candidate_user=args.reuse_candidate_user,
            output_dir=args.output_dir,
            enable_dedup=not args.no_dedup,
            reset_memory=not args.no_reset_memory,
            save_raw_snapshot=args.save_raw_snapshot,
        )
    )
    sys.stdout.write(json.dumps(report["paths"], ensure_ascii=False, indent=2) + "\n")
    return 0


def _should_project_candidate(candidate: CandidateView) -> bool:
    if candidate.view_type not in WRITEABLE_VIEW_TYPES:
        return False
    if candidate.view_type != "constraint" and candidate.forget_conflict:
        return False
    if candidate.view_type == "artifact_fact" and candidate.attribution_risk == "high":
        return True
    return True


def _candidate_write_trace_item(write_result: CandidateViewWriteResult) -> dict[str, Any]:
    return {
        "row_index": write_result.row_index,
        "turn_index": write_result.turn_index,
        "resource_id": write_result.resource_id,
        "written_category_ids": write_result.written_category_ids,
        "projections": [asdict(projection) for projection in write_result.projections],
    }

def _is_forget_question(preference: str) -> bool:
    normalized = str(preference or "").lower()
    return any(
        marker in normalized
        for marker in (
            "forget",
            "do not remember",
            "don't remember",
            "remove from memory",
            "deleted",
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
