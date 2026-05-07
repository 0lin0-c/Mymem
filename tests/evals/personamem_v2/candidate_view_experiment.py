from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.memory.writer import MemoryWriter
from tests.evals.personamem_v2.candidate_views import (
    PERSONA_ID,
    CandidateView,
    extract_candidate_views,
)
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
    _categories_for_prompt,
    _reset_user_memory,
    ensure_user_onboarded,
    evaluate_sample,
    resolve_existing_user,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("test_results") / "personamem_v2_candidate_experiment"
EXPERIMENT_PERSONA_ID = f"{PERSONA_ID}_candidate_views"
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
    """Keep original write turns intact and attach candidates as structured trace only."""
    candidates = []
    for candidate in extract_candidate_views(question):
        item = candidate.to_dict()
        item["writable"] = _should_project_candidate(candidate)
        candidates.append(item)
    return [
        PlannedCandidateTurn(
            row_index=question.row_index,
            turn_index=turn_index,
            user_input=user_input,
            assistant_response=assistant_response,
            candidates=candidates,
        )
        for turn_index, (user_input, assistant_response) in enumerate(
            snippet_to_turns(question),
            start=1,
        )
    ]


def clone_sample_for_candidate_experiment(sample: PersonaMemSample) -> PersonaMemSample:
    """Use a separate DB user while keeping the evaluated questions from persona 66."""
    return replace(
        sample,
        persona_id=EXPERIMENT_PERSONA_ID,
        user_key=f"personamem_v2_persona_{EXPERIMENT_PERSONA_ID}",
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
    user_id = await ensure_user_onboarded(
        session,
        sample,
        recreate_existing=reset_memory,
    )
    if reset_memory:
        await _reset_user_memory(session, user_id)

    llm = LLMFactory.get_provider()
    writer = MemoryWriter(session, llm, enable_dedup=enable_dedup)
    categories = await _categories_for_prompt(session, user_id)
    memory_count = 0
    candidate_trace: list[dict[str, Any]] = []

    for question in sample.questions:
        for planned in build_candidate_turn_plan(question):
            try:
                await writer.save_chat(
                    user_id=user_id,
                    user_input=planned.user_input,
                    assistant_response=planned.assistant_response,
                    modality="text",
                    user_categories=categories,
                )
                memory_count += 1
                candidate_trace.append(_candidate_trace_item(planned, status="written"))
                if memory_count % 10 == 0:
                    await session.commit()
            except Exception as exc:
                logger.exception(
                    "Failed to import PersonaMem candidate view: persona_id=%s row_index=%s",
                    question.persona_id,
                    question.row_index,
                )
                await session.rollback()
                candidate_trace.append(_candidate_trace_item(planned, status="error", error=str(exc)))

    await session.commit()
    return user_id, memory_count, candidate_trace


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
    save_raw_snapshot: bool = True,
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
    if save_raw_snapshot:
        save_rows_snapshot(rows, split=split)
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

        logger.info(
            "Running candidate-view trace/eval: persona_id=%s original_turn_count=%s mode=%s",
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
            candidate_trace = []
            logger.info(
                "Reusing existing candidate-view user: user_id=%s resources=%s",
                candidate_user_id,
                candidate_memory_count,
            )
        else:
            candidate_user_id, candidate_memory_count, candidate_trace = await import_candidate_view_sample(
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
    report = {
        "test_info": {
            "dataset": "bowen-upenn/PersonaMem-v2",
            "harness": "personamem_v2_candidate_view_trace_experiment",
            "persona_id": PERSONA_ID,
            "experiment_user_persona_id": EXPERIMENT_PERSONA_ID,
            "eval_mode": eval_mode.value,
            "top_k": top_k,
        },
        "baseline": baseline_summary,
        "candidate_view_trace": candidate_summary,
        "delta": summarize_report_delta(baseline_summary, candidate_summary),
        "candidate_projection": summarize_candidate_projection(sample),
        "candidate_trace": candidate_trace,
        "candidate_trace_errors": [
            item for item in candidate_trace if item.get("status") == "error"
        ],
    }
    json_path, markdown_path = save_candidate_experiment_report(report, output_dir)
    report["paths"] = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    return report


def summarize_candidate_projection(sample: PersonaMemSample) -> dict[str, Any]:
    original_turn_count = 0
    writable_candidate_count = 0
    writable_by_type = {view_type: 0 for view_type in sorted(WRITEABLE_VIEW_TYPES)}
    skipped_by_type: dict[str, int] = {}
    for question in sample.questions:
        original_turn_count += len(build_candidate_turn_plan(question))
        for candidate in extract_candidate_views(question):
            if _should_project_candidate(candidate):
                writable_candidate_count += 1
                writable_by_type[candidate.view_type] += 1
            else:
                skipped_by_type[candidate.view_type] = skipped_by_type.get(candidate.view_type, 0) + 1
    return {
        "original_turn_count": original_turn_count,
        "writable_candidate_count": writable_candidate_count,
        "writable_by_type": writable_by_type,
        "skipped_by_type": dict(sorted(skipped_by_type.items())),
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


def save_candidate_experiment_report(report: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = report["test_info"]["eval_mode"]
    json_path = output_dir / f"persona_{PERSONA_ID}_candidate_view_trace_{mode}_comparison.json"
    markdown_path = output_dir / f"persona_{PERSONA_ID}_candidate_view_trace_{mode}_comparison.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_candidate_experiment_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_candidate_experiment_markdown(report: dict[str, Any]) -> str:
    candidate_section = report.get("candidate_view_trace") or {}
    lines = [
        f"# PersonaMem-v2 Candidate View Trace Comparison - persona {report['test_info']['persona_id']}",
        "",
        f"- eval_mode: {report['test_info']['eval_mode']}",
        f"- top_k: {report['test_info']['top_k']}",
        "- candidate_views_write_mode: trace_only_original_turn_writes",
        "",
        "## Delta",
    ]
    for key, value in report["delta"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Baseline"])
    for key, value in report["baseline"]["metrics"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Candidate View Trace"])
    for key, value in candidate_section.get("metrics", {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Candidate Projection"])
    projection = report["candidate_projection"]
    lines.append(f"- original_turn_count: {projection['original_turn_count']}")
    lines.append(f"- writable_candidate_count: {projection['writable_candidate_count']}")
    for key, value in projection["writable_by_type"].items():
        lines.append(f"- writable_{key}: {value}")
    for key, value in projection["skipped_by_type"].items():
        lines.append(f"- skipped_{key}: {value}")
    errors = report.get("candidate_trace_errors", [])
    if errors:
        lines.extend(["", "## Candidate Trace Errors"])
        for item in errors:
            lines.append(
                f"- row_index={item.get('row_index')} turn_index={item.get('turn_index')}: {item.get('error')}"
            )
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
    parser.add_argument("--no-save-raw-snapshot", action="store_true")
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
            save_raw_snapshot=not args.no_save_raw_snapshot,
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


def _candidate_trace_item(
    planned: PlannedCandidateTurn,
    *,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    item = {
        "row_index": planned.row_index,
        "turn_index": planned.turn_index,
        "write_input": "original_turn",
        "status": status,
        "candidate_count": len(planned.candidates),
        "candidate_types": [
            candidate["view_type"] for candidate in planned.candidates
        ],
        "candidates": planned.candidates,
    }
    if error:
        item["error"] = error
    return item

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
