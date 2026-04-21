from __future__ import annotations

from typing import Any

from tests.evals.converted_data.categories import category_label, format_qa_category


def normalize_eval_mode(eval_mode: str | None) -> str:
    return eval_mode or "assistant_eval"


def get_trace_detail(q: dict[str, Any]) -> dict[str, Any]:
    return dict(q.get("trace_detail") or {})


def get_db_diagnosis(q: dict[str, Any]) -> dict[str, Any] | None:
    trace_detail = get_trace_detail(q)
    return q.get("db_diagnosis") or trace_detail.get("db_diagnosis")


def get_retrieval_layer(q: dict[str, Any]) -> dict[str, Any]:
    trace_detail = get_trace_detail(q)
    return dict(q.get("retrieval_layer") or trace_detail.get("retrieval_layer") or {})


def get_retrieved_contexts(q: dict[str, Any]) -> list[str]:
    trace_detail = get_trace_detail(q)
    return list(q.get("retrieved_contexts") or trace_detail.get("retrieved_contexts") or [])


def get_retrieved_scores(q: dict[str, Any]) -> list[float]:
    trace_detail = get_trace_detail(q)
    return list(q.get("retrieved_scores") or trace_detail.get("retrieved_scores") or [])


def flatten_qa_results(results_data: dict[str, Any]) -> list[dict[str, Any]]:
    all_qa: list[dict[str, Any]] = []
    for sample in results_data.get("samples", []):
        character = sample.get("character")
        sample_index = sample.get("sample_index")
        for q in sample.get("qa_results", []):
            q_copy = dict(q)
            q_copy.setdefault("character", character)
            q_copy.setdefault("sample_index", sample_index)
            all_qa.append(q_copy)
    return all_qa


def classify_answer_failure(q: dict[str, Any]) -> str:
    answer = str(q.get("generated_answer") or "").lower()
    expected = str(q.get("standard_answer") or "")
    retrieval_hit = q.get("retrieval_hit")
    storage_hit = q.get("storage_hit")

    if not expected.strip():
        return "empty_standard_answer"
    if storage_hit is False:
        return "storage_gap"
    if retrieval_hit is False:
        return "retrieval_gap"
    if "don't have enough information" in answer or "not have enough information" in answer:
        return "answer_abstained"
    db_diagnosis = get_db_diagnosis(q)
    if db_diagnosis:
        return str(db_diagnosis.get("diagnosis_type") or "diagnosed_failure")
    return "wrong_specific_answer"


def _rank_bucket(rank: int | None) -> str:
    if rank is None:
        return "miss"
    if rank == 1:
        return "top1"
    if rank <= 3:
        return "top3"
    if rank <= 5:
        return "top5"
    return "beyond_top5"


def calculate_metrics(results: list[Any], eval_mode: str | None = None) -> dict[str, Any]:
    return calculate_metrics_from_qa_dicts(
        [_result_to_qa_dict(result) for result in results],
        eval_mode=eval_mode,
    )


def _result_to_qa_dict(result: Any) -> dict[str, Any]:
    layer = getattr(result, "retrieval_layer", None)
    return {
        "eval_mode": getattr(result, "eval_mode", None),
        "question": getattr(result, "question", None),
        "standard_answer": getattr(result, "expected_answer", None),
        "generated_answer": getattr(result, "llm_answer", None),
        "is_correct": getattr(result, "is_correct", None),
        "category": getattr(result, "category", None),
        "storage_hit": getattr(result, "storage_hit", None),
        "retrieval_hit": getattr(result, "retrieval_hit", None),
        "rank_position": getattr(result, "rank_position", None),
        "retrieval_layer": {
            "resolved_layer": getattr(layer, "resolved_layer", "none"),
            "is_sufficient_at_category": getattr(layer, "is_sufficient_at_category", False),
            "llm_classified_categories": getattr(layer, "llm_classified_categories", []),
            "category_results_count": getattr(layer, "category_results_count", 0),
            "resource_results_count": getattr(layer, "resource_results_count", 0),
        },
        "retrieved_contexts": getattr(result, "retrieved_contexts", []),
        "retrieved_scores": getattr(result, "retrieved_scores", []),
        "db_diagnosis": getattr(result, "db_diagnosis", None),
        "error": getattr(result, "error", None),
    }


def calculate_metrics_from_qa_dicts(
    qa_results: list[dict[str, Any]],
    eval_mode: str | None = None,
) -> dict[str, Any]:
    mode = normalize_eval_mode(eval_mode or _infer_eval_mode(qa_results))
    base = _base_metrics(qa_results)
    if mode == "storage_eval":
        base.update(_storage_metrics(qa_results))
    elif mode == "retrieval_eval":
        base.update(_retrieval_metrics(qa_results))
    else:
        retrieval = _retrieval_metrics(qa_results)
        base.update(_assistant_metrics(qa_results, recall_at_k=retrieval["recall_at_k"]))
        base.update(retrieval)
        base.update(_storage_metrics(qa_results))
    return base


def _infer_eval_mode(qa_results: list[dict[str, Any]]) -> str:
    for q in qa_results:
        if q.get("eval_mode"):
            return str(q["eval_mode"])
    return "assistant_eval"


def _base_metrics(qa_results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [q for q in qa_results if q.get("is_correct") is not None]
    correct_count = sum(1 for q in evaluated if q.get("is_correct") is True)
    category_groups: dict[str, list[dict[str, Any]]] = {}
    for q in qa_results:
        category_groups.setdefault(str(q.get("category", "unknown")), []).append(q)

    category_accuracy = {}
    for category, items in category_groups.items():
        evaluated_items = [q for q in items if q.get("is_correct") is not None]
        correct = sum(1 for q in evaluated_items if q.get("is_correct") is True)
        category_accuracy[category] = {
            "label": category_label(category),
            "display_name": format_qa_category(category),
            "count": len(items),
            "correct": correct,
            "accuracy": correct / len(evaluated_items) * 100 if evaluated_items else 0,
        }

    return {
        "total_questions": len(qa_results),
        "evaluated_questions": len(evaluated),
        "correct_count": correct_count,
        "accuracy": correct_count / len(evaluated) * 100 if evaluated else 0,
        "category_accuracy": category_accuracy,
    }


def _storage_metrics(qa_results: list[dict[str, Any]]) -> dict[str, Any]:
    storage_checked = [q for q in qa_results if q.get("storage_hit") is not None]
    storage_hits = [q for q in storage_checked if q.get("storage_hit") is True]
    diagnosis_counts: dict[str, int] = {}
    for q in qa_results:
        diagnosis = (get_db_diagnosis(q) or {}).get("diagnosis_type")
        if diagnosis:
            diagnosis_counts[diagnosis] = diagnosis_counts.get(diagnosis, 0) + 1
    return {
        "storage_hit_count": len(storage_hits),
        "storage_coverage_rate": len(storage_hits) / len(storage_checked) * 100 if storage_checked else 0,
        "db_diagnosis_counts": diagnosis_counts,
    }


def _retrieval_metrics(qa_results: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_checked = [q for q in qa_results if q.get("retrieval_hit") is not None]
    retrieval_hits = [q for q in retrieval_checked if q.get("retrieval_hit") is True]
    ranks = [q.get("rank_position") for q in retrieval_hits if isinstance(q.get("rank_position"), int)]
    all_scores = [s for q in qa_results for s in get_retrieved_scores(q) if isinstance(s, (int, float))]

    layer_groups: dict[str, list[dict[str, Any]]] = {}
    rank_distribution: dict[str, int] = {}
    for q in qa_results:
        layer = get_retrieval_layer(q).get("resolved_layer", "none")
        layer_groups.setdefault(layer, []).append(q)
        rank_distribution[_rank_bucket(q.get("rank_position"))] = rank_distribution.get(_rank_bucket(q.get("rank_position")), 0) + 1

    layer_distribution = {}
    for layer, items in layer_groups.items():
        evaluated_items = [q for q in items if q.get("is_correct") is not None]
        correct = sum(1 for q in evaluated_items if q.get("is_correct") is True)
        hits = sum(1 for q in items if q.get("retrieval_hit") is True)
        layer_distribution[layer] = {
            "count": len(items),
            "rate": len(items) / len(qa_results) * 100 if qa_results else 0,
            "correct": correct,
            "accuracy": correct / len(evaluated_items) * 100 if evaluated_items else 0,
            "recall_at_k": hits / len(items) * 100 if items else 0,
        }

    return {
        "retrieval_hit_count": len(retrieval_hits),
        "recall_at_k": len(retrieval_hits) / len(retrieval_checked) * 100 if retrieval_checked else 0,
        "top1_hit_rate": sum(1 for rank in ranks if rank == 1) / len(retrieval_checked) * 100 if retrieval_checked else 0,
        "top3_hit_rate": sum(1 for rank in ranks if rank <= 3) / len(retrieval_checked) * 100 if retrieval_checked else 0,
        "top5_hit_rate": sum(1 for rank in ranks if rank <= 5) / len(retrieval_checked) * 100 if retrieval_checked else 0,
        "mean_first_evidence_rank": sum(ranks) / len(ranks) if ranks else 0,
        "rank_distribution": rank_distribution,
        "avg_retrieval_score": sum(all_scores) / len(all_scores) if all_scores else 0,
        "layer_distribution": layer_distribution,
    }


def _assistant_metrics(qa_results: list[dict[str, Any]], *, recall_at_k: float = 0) -> dict[str, Any]:
    evaluated = [q for q in qa_results if q.get("is_correct") is not None]
    non_empty_answer_evaluated = [
        q for q in evaluated
        if str(q.get("standard_answer") or "").strip()
    ]
    non_empty_answer_correct = sum(1 for q in non_empty_answer_evaluated if q.get("is_correct") is True)
    failure_patterns: dict[str, int] = {}
    for q in qa_results:
        if q.get("is_correct") is False:
            pattern = classify_answer_failure(q)
            failure_patterns[pattern] = failure_patterns.get(pattern, 0) + 1
    return {
        "answer_accuracy": _base_metrics(qa_results)["accuracy"],
        "non_empty_answer_questions": len(non_empty_answer_evaluated),
        "non_empty_answer_correct_count": non_empty_answer_correct,
        "adjusted_accuracy_excluding_empty_standard": (
            non_empty_answer_correct / len(non_empty_answer_evaluated) * 100
            if non_empty_answer_evaluated else 0
        ),
        "answer_failure_patterns": failure_patterns,
        "retrieval_support_rate": recall_at_k,
    }


def enrich_results_data_for_analysis(results_data: dict[str, Any]) -> dict[str, Any]:
    all_qa = flatten_qa_results(results_data)
    eval_mode = (results_data.get("test_info") or {}).get("eval_mode") or _infer_eval_mode(all_qa)
    rebuilt_metrics = calculate_metrics_from_qa_dicts(all_qa, eval_mode=eval_mode)

    statistics = dict(results_data.get("statistics") or {})
    for key, value in rebuilt_metrics.items():
        if key not in statistics or statistics.get(key) in ({}, None):
            statistics[key] = value

    wrong_cases = [q for q in all_qa if q.get("is_correct") is False]
    empty_standard_correct = [
        q for q in all_qa
        if q.get("is_correct") is True and not str(q.get("standard_answer") or "").strip()
    ]
    db_diag_present = sum(1 for q in all_qa if get_db_diagnosis(q) is not None)

    high_risk_notes: list[str] = []
    if eval_mode == "assistant_eval" and empty_standard_correct:
        high_risk_notes.append(
            "存在标准答案为空但回答被判正确的样本，主准确率需要结合 adjusted accuracy 解读。"
        )
    if wrong_cases and db_diag_present == 0:
        high_risk_notes.append(
            "错误样本没有 db_diagnosis，无法严格区分 storage/retrieval/generation 责任。"
        )

    enriched = dict(results_data)
    enriched["statistics"] = statistics
    enriched["analysis_summary"] = {
        "eval_mode": eval_mode,
        "wrong_count": len(wrong_cases),
        "empty_standard_correct_count": len(empty_standard_correct),
        "db_diagnosis_present_count": db_diag_present,
        "db_diagnosis_counts": statistics.get("db_diagnosis_counts", {}),
        "high_risk_notes": high_risk_notes,
    }
    return enriched
