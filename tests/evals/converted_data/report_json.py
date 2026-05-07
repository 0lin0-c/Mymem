from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.evals.converted_data.metrics import (
    calculate_metrics,
    calculate_metrics_from_qa_dicts,
    classify_answer_failure,
    classify_answer_support_type,
)

logger = logging.getLogger(__name__)


TEXT_PREVIEW_LENGTH = 160


SUMMARY_METRIC_KEYS = {
    "storage_eval": [
        "total_questions",
        "correct_count",
        "accuracy",
        "storage_coverage_rate",
        "category_accuracy",
    ],
    "retrieval_eval": [
        "total_questions",
        "correct_count",
        "accuracy",
        "recall_at_k",
        "top1_hit_rate",
        "top3_hit_rate",
        "top5_hit_rate",
        "storage_coverage_rate",
        "category_accuracy",
    ],
    "assistant_eval": [
        "total_questions",
        "correct_count",
        "accuracy",
        "adjusted_accuracy_excluding_empty_standard",
        "answer_failure_patterns",
        "answer_support_counts",
        "recall_at_k",
        "top1_hit_rate",
        "top3_hit_rate",
        "top5_hit_rate",
        "storage_coverage_rate",
        "category_accuracy",
    ],
}


class LiveResultWriter:
    """Real-time results writer for converted-data evaluation."""

    def __init__(self, output_dir: Path, prefix: str = "mymem_test", eval_mode: str | None = None):
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.eval_mode = eval_mode
        self.results_path = output_dir / f"{prefix}_results_{timestamp}.json"
        self._data = {
            "test_info": {
                "timestamp": timestamp,
                "eval_mode": eval_mode,
            },
            "statistics": {},
            "samples": [],
        }
        self._current_sample_index: int | None = None
        self._flush()

    def start_sample(
        self,
        sample_index: int,
        character: str,
        user_id: str,
        total_sessions: int,
        total_memories: int,
        total_questions: int,
    ) -> None:
        sample_data = {
            "sample_index": sample_index,
            "character": character,
            "total_memories": total_memories,
            "total_questions": total_questions,
            "completed_questions": 0,
            "status": "in_progress",
            "qa_results": [],
        }
        self._data["samples"].append(sample_data)
        self._current_sample_index = len(self._data["samples"]) - 1
        self._update_global_stats()
        self._flush()

    def add_qa_result(self, qa_data: dict[str, Any]) -> None:
        current_sample = self._get_current_sample()
        if current_sample is None:
            raise RuntimeError("Need to call start_sample() before add_qa_result().")

        current_sample["qa_results"].append(qa_data)
        current_sample["completed_questions"] = len(current_sample["qa_results"])
        self._update_global_stats()
        self._flush()

    def replace_current_sample_results(self, qa_results: list[dict[str, Any]]) -> None:
        current_sample = self._get_current_sample()
        if current_sample is None:
            raise RuntimeError("Need an active sample before replacing results.")

        current_sample["qa_results"] = list(qa_results)
        current_sample["completed_questions"] = len(current_sample["qa_results"])
        self._update_global_stats()
        self._flush()

    def finish_sample(self, status: str = "completed") -> None:
        current_sample = self._get_current_sample()
        if current_sample is not None:
            current_sample["status"] = status
            current_sample["completed_questions"] = len(current_sample["qa_results"])
            self._current_sample_index = None
            self._update_global_stats()
            self._flush()

    def _get_current_sample(self) -> dict[str, Any] | None:
        if self._current_sample_index is None:
            return None
        if self._current_sample_index >= len(self._data["samples"]):
            return None
        return self._data["samples"][self._current_sample_index]

    def _update_global_stats(self) -> None:
        all_qa = [q for sample in self._data["samples"] for q in sample["qa_results"]]
        metrics = calculate_metrics_from_qa_dicts(all_qa, eval_mode=self.eval_mode)
        self._data["statistics"] = _compact_statistics(metrics, self.eval_mode)

    def _flush(self) -> None:
        self.results_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def save_results_json(
    reports: list[Any],
    output_dir: Path,
    prefix: str = "mymem_test",
    eval_mode: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"{prefix}_results_{timestamp}.json"

    all_results = [result for report in reports for result in report.results]
    overall_metrics = calculate_metrics(all_results, eval_mode=eval_mode)
    results_data = {
        "test_info": {
            "timestamp": timestamp,
            "eval_mode": eval_mode,
        },
        "statistics": _compact_statistics(overall_metrics, eval_mode),
        "samples": [],
    }

    for report in reports:
        sample_data = {
            "sample_index": report.sample_index,
            "character": report.character,
            "total_memories": report.total_memories,
            "total_questions": report.total_questions,
            "completed_questions": len(report.results),
            "status": "completed",
            "qa_results": [],
        }
        for result in report.results:
            sample_data["qa_results"].append(_result_to_json_dict(result))
        results_data["samples"].append(sample_data)

    results_path.write_text(json.dumps(results_data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Detailed results saved to: %s", results_path)
    return results_path


def _result_to_json_dict(result: Any) -> dict[str, Any]:
    layer = result.retrieval_layer
    retrieved_contexts = list(result.retrieved_contexts[:5])
    retrieved_scores = [round(score, 4) for score in result.retrieved_scores[:5]]
    db_diagnosis = _compact_db_diagnosis(result.db_diagnosis)
    trace_summary = {
        "resolved_layer": layer.resolved_layer,
        "low_confidence_fallback": getattr(layer, "low_confidence_fallback", False),
        "top_contexts": retrieved_contexts[:2],
        "top_scores": retrieved_scores[:2],
        "diagnosis_type": (db_diagnosis or {}).get("diagnosis_type"),
    }
    trace_detail = {
        "evaluation_trace": result.evaluation_trace,
        "retrieval_layer": {
            "resolved_layer": layer.resolved_layer,
            "is_sufficient_at_category": layer.is_sufficient_at_category,
            "llm_classified_categories": layer.llm_classified_categories,
            "category_results_count": layer.category_results_count,
            "resource_results_count": layer.resource_results_count,
            "low_confidence_fallback": getattr(layer, "low_confidence_fallback", False),
        },
        "retrieved_contexts": retrieved_contexts,
        "retrieved_scores": retrieved_scores,
        "db_diagnosis": db_diagnosis,
        "correctness_explanation": result.correctness_explanation,
        "evidence": result.evidence,
    }
    result_dict = {
        "question": result.question,
        "standard_answer": result.expected_answer,
        "generated_answer": result.llm_answer,
        "is_correct": result.is_correct,
        "category": result.category,
        "storage_hit": result.storage_hit,
        "retrieval_hit": result.retrieval_hit,
        "rank_position": result.rank_position,
        "answer_support_type": classify_answer_support_type(
            {
                "question": result.question,
                "standard_answer": result.expected_answer,
                "is_correct": result.is_correct,
                "retrieval_hit": result.retrieval_hit,
            }
        ),
        "failure_type": (
            "none"
            if result.is_correct is True
            else classify_answer_failure(
                {
                    "standard_answer": result.expected_answer,
                    "generated_answer": result.llm_answer,
                    "storage_hit": result.storage_hit,
                    "retrieval_hit": result.retrieval_hit,
                    "db_diagnosis": db_diagnosis,
                }
            )
        ),
        "trace_summary": trace_summary,
        "trace_detail": trace_detail,
        **({"error": result.error} if result.error else {}),
    }
    return result_dict


def _compact_statistics(metrics: dict[str, Any], eval_mode: str | None) -> dict[str, Any]:
    mode = eval_mode or "assistant_eval"
    keys = SUMMARY_METRIC_KEYS.get(mode, SUMMARY_METRIC_KEYS["assistant_eval"])
    return {key: metrics[key] for key in keys if key in metrics}


def _compact_db_diagnosis(db_diagnosis: dict[str, Any] | None) -> dict[str, Any] | None:
    if not db_diagnosis:
        return db_diagnosis

    compacted = {
        "diagnosis_type": db_diagnosis.get("diagnosis_type"),
        "summary": db_diagnosis.get("summary"),
        "matched_in_retrieved": _compact_memory_diagnosis_list(db_diagnosis.get("matched_in_retrieved")),
        "missed_in_retrieval": _compact_memory_diagnosis_list(db_diagnosis.get("missed_in_retrieval")),
        "llm_verification": db_diagnosis.get("llm_verification"),
    }
    always_keep = {"matched_in_retrieved", "missed_in_retrieval"}
    return {
        key: value
        for key, value in compacted.items()
        if key in always_keep or value not in (None, [], {}, "")
    }


def _compact_memory_diagnosis_list(memories: Any) -> list[dict[str, Any]]:
    if not memories:
        return []

    compacted_items: list[dict[str, Any]] = []
    for memory in memories:
        if not isinstance(memory, dict):
            continue
        compacted_item = {
            "id": memory.get("id"),
            "source": memory.get("source"),
            "importance_score": memory.get("importance_score"),
            "updated_at": memory.get("updated_at"),
            "matched_keyword": memory.get("matched_keyword"),
            "text_preview": _make_text_preview(memory.get("text")),
        }
        compacted_items.append(
            {key: value for key, value in compacted_item.items() if value not in (None, "")}
        )
    return compacted_items


def _make_text_preview(text: Any) -> str:
    raw_text = str(text or "").strip()
    if not raw_text:
        return ""
    if len(raw_text) <= TEXT_PREVIEW_LENGTH:
        return raw_text
    return raw_text[: TEXT_PREVIEW_LENGTH - 3].rstrip() + "..."
