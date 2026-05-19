from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.evals.common import RESULT_SCHEMA_VERSION, build_run_manifest
from tests.evals.converted_data.metrics import calculate_metrics
from tests.evals.converted_data.report_json import _compact_db_diagnosis
from tests.evals.personamem_v2.analysis import (
    analyze_personamem_evidence,
    build_personamem_analysis_markdown,
    calculate_personamem_stage_metrics,
)
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
        ),
    }
    data = add_personamem_statistics(data)
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
        }
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
        "retrieval_changed_answer_same": 0,
        "retrieval_same_answer_changed": 0,
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
    return comparison


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
