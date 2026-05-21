from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.evals.common import RESULT_SCHEMA_VERSION, build_run_manifest, finalize_run_manifest
from tests.evals.converted_data.metrics import calculate_metrics
from tests.evals.converted_data.report_json import _compact_db_diagnosis
from tests.evals.personamem_v2.analysis import (
    analyze_personamem_evidence,
    build_personamem_analysis_markdown,
    calculate_personamem_stage_metrics,
)
from tests.evals.personamem_v2.bucket_schema import (
    bucket_schema_payload,
    classify_with_bucket_schema,
)
from tests.evals.personamem_v2.report_contract import mark_report_contract
from tests.evals.personamem_v2.models import PersonaMemReport, PersonaMemResult


def save_results_json(
    reports: list[PersonaMemReport],
    output_dir: Path,
    eval_mode: str,
    test_info: dict[str, Any] | None = None,
    run_manifest: dict[str, Any] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"personamem_v2_{eval_mode}_results_{timestamp}.json"
    all_results = [result for report in reports for result in report.results]
    info = {
        "timestamp": timestamp,
        "dataset": "bowen-upenn/PersonaMem-v2",
        "harness": "personamem_v2",
        "eval_mode": eval_mode,
    }
    if test_info:
        info.update(test_info)
    data = {
        "test_info": info,
        "statistics": calculate_metrics(all_results, eval_mode=eval_mode),
        "samples": [_report_to_dict(report) for report in reports],
        "run_manifest": run_manifest
        or build_run_manifest(
            harness="personamem_v2",
            eval_mode=eval_mode,
            dataset="bowen-upenn/PersonaMem-v2",
            question_count=len(all_results),
            chat_model=info.get("chat_model"),
            evaluator_model=info.get("evaluator_model"),
            evaluator_isolated=info.get("evaluator_isolated"),
            top_k=info.get("top_k"),
            scoring_config=info.get("scoring_config"),
            rerank_config=info.get("rerank_config"),
            dataset_hash=info.get("dataset_hash"),
            cache_hash=info.get("cache_hash"),
            temperature=info.get("temperature", 0),
        ),
    }
    data = add_personamem_statistics(data)
    finalize_run_manifest(data["run_manifest"], result_file_path=results_path)
    mark_report_contract(data)
    results_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return results_path


def save_analysis_markdown(results_path: Path) -> Path | None:
    results_data = json.loads(results_path.read_text(encoding="utf-8"))
    analysis_path = results_path.with_name(f"{results_path.stem}_analysis.md")
    analysis_path.write_text(
        build_personamem_analysis_markdown(results_data, results_path.name),
        encoding="utf-8",
    )
    return analysis_path


def _report_to_dict(report: PersonaMemReport) -> dict[str, Any]:
    return {
        "sample_index": report.sample_index,
        "persona_id": report.character,
        "user_id": report.user_id,
        "db_snapshot_id": report.db_snapshot_id,
        "chat_model": report.chat_model,
        "total_sessions": report.total_sessions,
        "total_memories": report.total_memories,
        "total_questions": report.total_questions,
        "evaluator_model": report.evaluator_model,
        "evaluator_isolated": report.evaluator_isolated,
        "qa_results": [_result_to_dict(result) for result in report.results],
    }


def _result_to_dict(result: PersonaMemResult) -> dict[str, Any]:
    db_diagnosis = _compact_db_diagnosis(result.db_diagnosis)
    layer = result.retrieval_layer
    retrieval_stage = analyze_personamem_evidence(
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
    )
    answer_stage = analyze_personamem_evidence(
        question=result.question,
        correct_answer=result.expected_answer,
        supporting_preference=result.preference,
        related_conversation_snippet=result.related_conversation_snippet,
        incorrect_answers=result.incorrect_answers,
        contexts=result.retrieved_contexts,
        scores=result.retrieved_scores,
        stage="answer_context",
        loose_rank_position=result.rank_position,
        retrieval_hit_loose=result.retrieval_hit,
        generated_answer=result.llm_answer,
        is_correct=result.is_correct,
    )
    return {
        "persona_id": result.persona_id,
        "source_split": result.source_split,
        "row_index": result.row_index,
        "question": result.question,
        "standard_answer": result.expected_answer,
        "generated_answer": result.llm_answer,
        "is_correct": result.is_correct,
        "storage_hit": result.storage_hit,
        "retrieval_hit": result.retrieval_hit,
        "rank_position": result.rank_position,
        "retrieval_hit_loose": retrieval_stage["retrieval_hit_loose"],
        "loose_rank_position": retrieval_stage["loose_rank_position"],
        "pref_type": result.pref_type,
        "updated": result.updated,
        "who": result.who,
        "correct_answer": result.expected_answer,
        "incorrect_answers": result.incorrect_answers,
        "supporting_preference": result.preference,
        "related_conversation_snippet": result.related_conversation_snippet,
        "evidence": result.evidence,
        "retrieval_layer": {
            "resolved_layer": layer.resolved_layer,
            "llm_classified_categories": layer.llm_classified_categories,
            "is_sufficient_at_category": layer.is_sufficient_at_category,
            "category_results_count": layer.category_results_count,
            "resource_results_count": layer.resource_results_count,
            "low_confidence_fallback": layer.low_confidence_fallback,
        },
        "retrieval_stage": retrieval_stage,
        "answer_stage": answer_stage,
        "answer_support_type": answer_stage["answer_support_type"],
        "retrieved_contexts": result.retrieved_contexts,
        "retrieved_contexts_preview": result.retrieved_contexts[:5],
        "retrieved_scores": [round(score, 4) for score in result.retrieved_scores],
        "retrieved_scores_preview": [round(score, 4) for score in result.retrieved_scores[:5]],
        "db_diagnosis": db_diagnosis,
        "correctness_explanation": result.correctness_explanation,
        "evaluation_trace": result.evaluation_trace,
        **({"error": result.error} if result.error else {}),
    }


def add_personamem_statistics(data: dict[str, Any]) -> dict[str, Any]:
    qa_results = [
        qa
        for sample in data.get("samples", [])
        for qa in sample.get("qa_results", [])
    ]
    statistics = dict(data.get("statistics") or {})
    statistics.update(build_personamem_statistics_from_qa_results(qa_results, statistics))
    data["statistics"] = statistics
    if isinstance(data.get("run_manifest"), dict):
        data["run_manifest"].setdefault("result_schema_version", RESULT_SCHEMA_VERSION)
    return data


def build_personamem_statistics_from_qa_results(
    qa_results: list[dict[str, Any]],
    overall_statistics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retrieval_stage = calculate_personamem_stage_metrics(
        qa_results,
        stage_key="retrieval_stage",
    )
    answer_stage = calculate_personamem_stage_metrics(
        qa_results,
        stage_key="answer_stage",
    )
    overall_accuracy = None
    if overall_statistics:
        overall_accuracy = overall_statistics.get("accuracy", overall_statistics.get("answer_accuracy"))
    evidence_first_summary = build_evidence_first_summary(
        retrieval_metrics=retrieval_stage,
        answer_metrics=answer_stage,
        overall_accuracy=overall_accuracy,
    )
    return {
        "personamem_evidence": {
            "retrieval_stage": retrieval_stage,
            "answer_stage": answer_stage,
            "evidence_first_summary": evidence_first_summary,
        },
        "bucket_schema": bucket_schema_payload(),
        "bucket_report": build_bucket_report(qa_results),
    }


def build_evidence_first_summary(
    *,
    retrieval_metrics: dict[str, Any],
    answer_metrics: dict[str, Any],
    overall_accuracy: float | None,
) -> dict[str, Any]:
    answerable = float(retrieval_metrics.get("answerable_context_hit_at_k", 0) or 0)
    accuracy = float(
        overall_accuracy
        if overall_accuracy is not None
        else answer_metrics.get("answer_accuracy", answer_metrics.get("accuracy", 0)) or 0
    )
    summary = {
        "primary_metrics": {
            "answerable_context_hit_at_k": answerable,
            "target_preference_hit_at_k": float(retrieval_metrics.get("target_preference_hit_at_k", 0) or 0),
            "target_answer_anchor_hit_at_k": float(
                retrieval_metrics.get("target_answer_anchor_hit_at_k", 0) or 0
            ),
            "wrong_neighbor_substitution_rate": float(
                retrieval_metrics.get("wrong_neighbor_substitution_rate", 0) or 0
            ),
            "target_evidence_not_retrieved_rate": float(
                retrieval_metrics.get("target_evidence_not_retrieved_rate", 0) or 0
            ),
            "loose_vs_answerable_gap": float(retrieval_metrics.get("loose_vs_answerable_gap", 0) or 0),
            "accuracy": accuracy,
        },
        "diagnostic_labels": [],
    }
    if accuracy - answerable >= 15:
        summary["diagnostic_labels"].append("generation_masking_retrieval_gap")
    if (retrieval_metrics.get("wrong_neighbor_substitution_rate", 0) or 0) >= 20:
        summary["diagnostic_labels"].append("wrong_neighbor_substitution_risk")
    if (retrieval_metrics.get("target_evidence_not_retrieved_rate", 0) or 0) >= 20:
        summary["diagnostic_labels"].append("target_evidence_not_retrieved_risk")
    return summary


def build_model_sweep_ranking_key(item: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
    summary = (
        item.get("personamem_metrics", {})
        .get("personamem_evidence", {})
        .get("evidence_first_summary", {})
        .get("primary_metrics", {})
    )
    return (
        float(summary.get("answerable_context_hit_at_k", 0) or 0),
        float(summary.get("target_preference_hit_at_k", 0) or 0),
        float(summary.get("target_answer_anchor_hit_at_k", 0) or 0),
        -float(summary.get("wrong_neighbor_substitution_rate", 0) or 0),
        -float(summary.get("target_evidence_not_retrieved_rate", 0) or 0),
        float(summary.get("accuracy", 0) or 0),
    )


def build_paired_comparison(
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_map = {_comparison_key(item): item for item in baseline}
    candidate_map = {_comparison_key(item): item for item in candidate}
    shared_keys = sorted(set(baseline_map) & set(candidate_map))
    comparison = {
        "shared_questions": len(shared_keys),
        "gain": 0,
        "regression": 0,
        "stable_success": 0,
        "stable_failure": 0,
        "evidence_gain": 0,
        "evidence_regression": 0,
        "evidence_stable_success": 0,
        "evidence_stable_failure": 0,
        "retrieval_changed_answer_same": 0,
        "retrieval_same_answer_changed": 0,
        "per_row": [],
        "bucket_report": {},
        "statistical_confidence": {},
    }
    for key in shared_keys:
        left = baseline_map[key]
        right = candidate_map[key]
        left_correct = left.get("is_correct") is True
        right_correct = right.get("is_correct") is True
        left_answerable = (left.get("retrieval_stage") or {}).get("answerable_context_hit") is True
        right_answerable = (right.get("retrieval_stage") or {}).get("answerable_context_hit") is True
        if not left_correct and right_correct:
            comparison["gain"] += 1
        elif left_correct and not right_correct:
            comparison["regression"] += 1
        elif left_correct and right_correct:
            comparison["stable_success"] += 1
        else:
            comparison["stable_failure"] += 1
        if left_answerable != right_answerable and left_correct == right_correct:
            comparison["retrieval_changed_answer_same"] += 1
        if left_answerable == right_answerable and left_correct != right_correct:
            comparison["retrieval_same_answer_changed"] += 1
        if not left_answerable and right_answerable:
            comparison["evidence_gain"] += 1
        elif left_answerable and not right_answerable:
            comparison["evidence_regression"] += 1
        elif left_answerable and right_answerable:
            comparison["evidence_stable_success"] += 1
        else:
            comparison["evidence_stable_failure"] += 1
        comparison["per_row"].append(
            {
                "comparison_key": key,
                "persona_id": right.get("persona_id") or left.get("persona_id"),
                "source_split": right.get("source_split") or left.get("source_split"),
                "row_index": right.get("row_index") if right.get("row_index") is not None else left.get("row_index"),
                "question": right.get("question") or left.get("question"),
                "bucket": classify_personamem_eval_bucket(right or left),
                "baseline_is_correct": left_correct,
                "candidate_is_correct": right_correct,
                "baseline_answerable_context_hit": left_answerable,
                "candidate_answerable_context_hit": right_answerable,
                "answer_outcome": _paired_outcome(left_correct, right_correct),
                "evidence_outcome": _paired_outcome(left_answerable, right_answerable),
            }
        )
    comparison["bucket_report"] = build_paired_bucket_report(comparison["per_row"])
    comparison["statistical_confidence"] = build_statistical_confidence(comparison)
    return comparison


def build_bucket_report(qa_results: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in qa_results:
        bucket, bucket_source = classify_with_bucket_schema(item)
        entry = buckets.setdefault(
            bucket,
            {
                "sample_count": 0,
                "bucket_schema_version": bucket_source["bucket_schema_version"],
                "evidence_source": bucket_source["evidence_source"],
                "matched_patterns": set(),
                "answer_correct_count": 0,
                "answerable_context_hit_count": 0,
                "target_answer_anchor_hit_count": 0,
                "wrong_neighbor_substitution_count": 0,
                "target_evidence_not_retrieved_count": 0,
                "negative_constraint_only_count": 0,
                "empty_gold_count": 0,
            },
        )
        stage = item.get("retrieval_stage") or {}
        entry["sample_count"] += 1
        entry["matched_patterns"].update(bucket_source["matched_patterns"])
        entry["answer_correct_count"] += int(item.get("is_correct") is True)
        entry["answerable_context_hit_count"] += int(stage.get("answerable_context_hit") is True)
        entry["target_answer_anchor_hit_count"] += int(stage.get("target_answer_anchor_hit") is True)
        subtype = str(stage.get("retrieval_failure_subtype") or "")
        support = str(stage.get("answer_support_type") or "")
        entry["wrong_neighbor_substitution_count"] += int(subtype == "wrong_neighbor_substitution")
        entry["target_evidence_not_retrieved_count"] += int(subtype == "target_evidence_not_retrieved")
        entry["negative_constraint_only_count"] += int(
            subtype == "negative_constraint_only" or support == "negative_constraint_only"
        )
        entry["empty_gold_count"] += int(not str(item.get("standard_answer") or item.get("correct_answer") or "").strip())
    for entry in buckets.values():
        entry["matched_patterns"] = sorted(entry["matched_patterns"])
        total = entry["sample_count"] or 1
        entry["answer_accuracy"] = entry["answer_correct_count"] / total * 100
        entry["evidence_hit_rate"] = entry["answerable_context_hit_count"] / total * 100
        entry["target_answer_anchor_hit_rate"] = entry["target_answer_anchor_hit_count"] / total * 100
        entry["wrong_neighbor_substitution_rate"] = entry["wrong_neighbor_substitution_count"] / total * 100
        entry["target_evidence_not_retrieved_rate"] = entry["target_evidence_not_retrieved_count"] / total * 100
    return dict(sorted(buckets.items()))


def build_paired_bucket_report(per_row: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in per_row:
        entry = buckets.setdefault(
            row["bucket"],
            {
                "sample_count": 0,
                "win": 0,
                "loss": 0,
                "stable_success": 0,
                "stable_failure": 0,
                "evidence_win": 0,
                "evidence_loss": 0,
                "evidence_stable_success": 0,
                "evidence_stable_failure": 0,
            },
        )
        entry["sample_count"] += 1
        answer_key = _outcome_bucket_key(row["answer_outcome"], prefix="")
        evidence_key = _outcome_bucket_key(row["evidence_outcome"], prefix="evidence_")
        entry[answer_key] += 1
        entry[evidence_key] += 1
    return dict(sorted(buckets.items()))


def build_statistical_confidence(paired_comparison: dict[str, Any]) -> dict[str, Any]:
    win = int(paired_comparison.get("gain", 0) or 0)
    loss = int(paired_comparison.get("regression", 0) or 0)
    evidence_win = int(paired_comparison.get("evidence_gain", 0) or 0)
    evidence_loss = int(paired_comparison.get("evidence_regression", 0) or 0)
    return {
        "answer_paired_win_loss": _paired_confidence(win, loss),
        "evidence_paired_win_loss": _paired_confidence(evidence_win, evidence_loss),
        "method": "normal_approximation_for_paired_win_loss; diagnostic_for_small_n",
    }


def classify_personamem_eval_bucket(item: dict[str, Any]) -> str:
    bucket, _source = classify_with_bucket_schema(item)
    return bucket


def determine_experiment_conclusion(
    paired_comparison: dict[str, Any],
    *,
    changed_variables: list[str] | tuple[str, ...],
) -> str:
    unique_variables = {value for value in changed_variables if value}
    if len(unique_variables) != 1:
        return "diagnostic_only"
    gain = int(paired_comparison.get("gain", 0) or 0)
    regression = int(paired_comparison.get("regression", 0) or 0)
    if gain == 0 and regression == 0:
        return "inconclusive"
    if gain > regression:
        return "accept"
    if regression > gain:
        return "reject"
    return "inconclusive"


def _comparison_key(item: dict[str, Any]) -> str:
    return "|".join(
        [
            str(item.get("persona_id") or item.get("character") or ""),
            str(item.get("source_split") or ""),
            str(item.get("row_index") or ""),
            str(item.get("question") or ""),
        ]
    )


def _paired_outcome(left: bool, right: bool) -> str:
    if not left and right:
        return "win"
    if left and not right:
        return "loss"
    if left and right:
        return "stable_success"
    return "stable_failure"


def _outcome_bucket_key(outcome: str, *, prefix: str) -> str:
    if outcome == "win":
        return f"{prefix}win"
    if outcome == "loss":
        return f"{prefix}loss"
    if outcome == "stable_success":
        return f"{prefix}stable_success"
    return f"{prefix}stable_failure"


def _paired_confidence(win: int, loss: int) -> dict[str, Any]:
    n = win + loss
    delta = win - loss
    if n == 0:
        return {
            "win": win,
            "loss": loss,
            "paired_delta": delta,
            "discordant_n": 0,
            "normal_approx_ci_95": [0, 0],
            "mcnemar_chi_square": None,
            "decision_strength": "inconclusive",
        }
    # Normal approximation over paired +/-1 discordant outcomes; useful as an explicit diagnostic,
    # not as a replacement for a larger formal benchmark.
    proportion = delta / n
    standard_error = ((1 - proportion**2) / n) ** 0.5
    low = round((proportion - 1.96 * standard_error) * n, 3)
    high = round((proportion + 1.96 * standard_error) * n, 3)
    chi_square = round(((abs(win - loss) - 1) ** 2) / n, 4) if n else None
    if n < 30:
        strength = "diagnostic_small_sample"
    elif low > 0:
        strength = "candidate_win_supported"
    elif high < 0:
        strength = "candidate_regression_supported"
    else:
        strength = "inconclusive"
    return {
        "win": win,
        "loss": loss,
        "paired_delta": delta,
        "discordant_n": n,
        "normal_approx_ci_95": [low, high],
        "mcnemar_chi_square": chi_square,
        "decision_strength": strength,
    }
