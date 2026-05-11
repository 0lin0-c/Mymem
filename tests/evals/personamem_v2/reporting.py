from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

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
    statistics["personamem_evidence"] = {
        "retrieval_stage": calculate_personamem_stage_metrics(
            qa_results,
            stage_key="retrieval_stage",
        ),
        "answer_stage": calculate_personamem_stage_metrics(
            qa_results,
            stage_key="answer_stage",
        ),
    }
    data["statistics"] = statistics
    return data
