from __future__ import annotations

import re
from collections import Counter
from typing import Any


TOP_K_BUCKETS = (1, 3, 5)

_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "answer",
    "because",
    "before",
    "being",
    "could",
    "does",
    "doing",
    "during",
    "from",
    "have",
    "having",
    "into",
    "just",
    "like",
    "might",
    "more",
    "most",
    "need",
    "needs",
    "only",
    "question",
    "should",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "user",
    "users",
}

_NEGATIVE_CONSTRAINT_TERMS = {
    "forget",
    "forgot",
    "forgotten",
    "do not remember",
    "don't remember",
    "ignore",
    "delete",
    "deleted",
    "remove",
    "removed",
    "retract",
    "retracted",
    "outdated",
}

_SENSITIVE_TERMS = {
    "allergy",
    "allergic",
    "asthma",
    "appendectomy",
    "doctor",
    "health",
    "medical",
    "medication",
    "password",
    "payment",
    "sensitive",
    "surgery",
}


def analyze_personamem_evidence(
    *,
    question: str,
    correct_answer: str,
    supporting_preference: str,
    related_conversation_snippet: str,
    incorrect_answers: list[str] | None,
    contexts: list[str],
    stage: str,
    scores: list[float] | None = None,
    loose_rank_position: int | None = None,
    retrieval_hit_loose: bool | None = None,
    generated_answer: str | None = None,
    is_correct: bool | None = None,
) -> dict[str, Any]:
    """Deterministic PersonaMem-v2 target-evidence analysis for any ranked context list."""
    del scores
    normalized_contexts = [_normalize_text(context) for context in contexts]
    preference_rank = _first_rank(normalized_contexts, supporting_preference, mode="preference")
    snippet_rank = _first_rank(normalized_contexts, related_conversation_snippet, mode="snippet")
    answer_anchor_rank = _first_rank(normalized_contexts, correct_answer, mode="answer")
    answerable_rank = _answerable_rank(
        preference_rank=preference_rank,
        snippet_rank=snippet_rank,
        answer_anchor_rank=answer_anchor_rank,
        correct_answer=correct_answer,
        supporting_preference=supporting_preference,
    )
    support_type = classify_personamem_answer_support_type(
        is_correct=is_correct,
        preference_rank=preference_rank,
        snippet_rank=snippet_rank,
        answer_anchor_rank=answer_anchor_rank,
        answerable_rank=answerable_rank,
        supporting_preference=supporting_preference,
        correct_answer=correct_answer,
    )
    failure_subtype = classify_personamem_failure_subtype(
        question=question,
        correct_answer=correct_answer,
        supporting_preference=supporting_preference,
        incorrect_answers=incorrect_answers or [],
        generated_answer=generated_answer,
        is_correct=is_correct,
        retrieval_hit_loose=retrieval_hit_loose,
        loose_rank_position=loose_rank_position,
        preference_rank=preference_rank,
        snippet_rank=snippet_rank,
        answer_anchor_rank=answer_anchor_rank,
        answerable_rank=answerable_rank,
        contexts=contexts,
    )
    k = len(contexts)
    topk_metrics = _topk_metrics(
        k=k,
        loose_rank_position=loose_rank_position,
        preference_rank=preference_rank,
        snippet_rank=snippet_rank,
        answer_anchor_rank=answer_anchor_rank,
        answerable_rank=answerable_rank,
    )
    return {
        "stage": stage,
        "context_count": k,
        "retrieval_hit_loose": bool(retrieval_hit_loose)
        if retrieval_hit_loose is not None
        else loose_rank_position is not None,
        "loose_rank_position": loose_rank_position,
        "target_preference_hit": preference_rank is not None,
        "target_preference_rank": preference_rank,
        "target_snippet_hit": snippet_rank is not None,
        "target_snippet_rank": snippet_rank,
        "target_answer_anchor_hit": answer_anchor_rank is not None,
        "target_answer_anchor_rank": answer_anchor_rank,
        "answerable_context_hit": answerable_rank is not None,
        "answerable_context_rank": answerable_rank,
        "target_evidence_source": _target_evidence_source(
            preference_rank,
            snippet_rank,
            answer_anchor_rank,
        ),
        "answer_support_type": support_type,
        "retrieval_failure_subtype": failure_subtype,
        "distractor_answer_leak": _has_distractor_leak(generated_answer, incorrect_answers or []),
        "sensitive_or_health_question": _contains_any(
            " ".join([question, correct_answer, supporting_preference, related_conversation_snippet]),
            _SENSITIVE_TERMS,
        ),
        "topk_metrics": topk_metrics,
    }


def classify_personamem_answer_support_type(
    *,
    is_correct: bool | None,
    preference_rank: int | None,
    snippet_rank: int | None,
    answer_anchor_rank: int | None,
    answerable_rank: int | None,
    supporting_preference: str,
    correct_answer: str,
) -> str:
    if is_correct is False:
        return "wrong"
    if not str(correct_answer or "").strip():
        return "unknown"
    if preference_rank is not None and answer_anchor_rank is not None:
        return "direct_preference"
    if snippet_rank is not None and answer_anchor_rank is not None:
        return "direct_snippet"
    if answer_anchor_rank is not None:
        return "answer_anchor"
    if preference_rank is not None and _is_negative_constraint(supporting_preference):
        return "negative_constraint_only"
    if answerable_rank is not None:
        return "partial_context"
    if is_correct is True:
        return "unsupported"
    return "unknown"


def classify_personamem_failure_subtype(
    *,
    question: str,
    correct_answer: str,
    supporting_preference: str,
    incorrect_answers: list[str],
    generated_answer: str | None,
    is_correct: bool | None,
    retrieval_hit_loose: bool | None,
    loose_rank_position: int | None,
    preference_rank: int | None,
    snippet_rank: int | None,
    answer_anchor_rank: int | None,
    answerable_rank: int | None,
    contexts: list[str],
) -> str:
    if is_correct is True and answerable_rank is not None:
        return "none"
    if _has_distractor_leak(generated_answer, incorrect_answers):
        return "distractor_answer_leak"
    loose_hit = bool(retrieval_hit_loose) if retrieval_hit_loose is not None else loose_rank_position is not None
    if loose_hit and answerable_rank is None:
        if preference_rank is not None and _is_negative_constraint(supporting_preference):
            return "negative_constraint_only"
        if _same_domain_wrong_neighbor(question, correct_answer, supporting_preference, contexts):
            return "wrong_neighbor_substitution"
        return "loose_hit_false_positive"
    if preference_rank is None and supporting_preference:
        return "target_evidence_not_retrieved"
    if answer_anchor_rank is None and preference_rank is not None:
        return "generation_missed_key_detail" if is_correct is False else "partial_context"
    if answerable_rank is not None and is_correct is False:
        return "generation_missed_key_detail"
    if _contains_any(" ".join([question, correct_answer, supporting_preference]), _SENSITIVE_TERMS):
        return "sensitive_policy_gap"
    return "unknown"


def calculate_personamem_stage_metrics(
    qa_results: list[dict[str, Any]],
    *,
    stage_key: str,
) -> dict[str, Any]:
    analyses = [q.get(stage_key) or {} for q in qa_results if isinstance(q.get(stage_key), dict)]
    total = len(analyses)
    if not total:
        return {}

    def pct(count: int) -> float:
        return count / total * 100 if total else 0

    answerable = sum(1 for item in analyses if item.get("answerable_context_hit"))
    loose = sum(1 for item in analyses if item.get("retrieval_hit_loose"))
    support_counts = Counter(str(item.get("answer_support_type") or "unknown") for item in analyses)
    failure_counts = Counter(str(item.get("retrieval_failure_subtype") or "unknown") for item in analyses)
    metrics = {
        "total_questions": total,
        "loose_recall_at_k": pct(loose),
        "target_preference_hit_at_k": pct(
            sum(1 for item in analyses if item.get("target_preference_hit"))
        ),
        "target_snippet_hit_at_k": pct(sum(1 for item in analyses if item.get("target_snippet_hit"))),
        "target_answer_anchor_hit_at_k": pct(
            sum(1 for item in analyses if item.get("target_answer_anchor_hit"))
        ),
        "answerable_context_hit_at_k": pct(answerable),
        "loose_vs_answerable_gap": pct(loose) - pct(answerable),
        "answer_support_type_counts": dict(support_counts),
        "retrieval_failure_subtype_counts": dict(failure_counts),
        "distractor_answer_leak_count": sum(
            1 for item in analyses if item.get("distractor_answer_leak")
        ),
    }
    metrics["wrong_neighbor_substitution_rate"] = pct(
        failure_counts.get("wrong_neighbor_substitution", 0)
    )
    metrics["target_evidence_not_retrieved_rate"] = pct(
        failure_counts.get("target_evidence_not_retrieved", 0)
    )
    for k in TOP_K_BUCKETS:
        metrics[f"target_preference_hit_at_{k}"] = pct(
            sum(1 for item in analyses if _rank_within(item.get("target_preference_rank"), k))
        )
        metrics[f"target_answer_anchor_hit_at_{k}"] = pct(
            sum(1 for item in analyses if _rank_within(item.get("target_answer_anchor_rank"), k))
        )
        metrics[f"answerable_context_hit_at_{k}"] = pct(
            sum(1 for item in analyses if _rank_within(item.get("answerable_context_rank"), k))
        )
    return metrics


def build_personamem_analysis_markdown(
    results_data: dict[str, Any],
    source_name: str,
) -> str:
    qa_results = _flatten_personamem_results(results_data)
    stats = results_data.get("statistics") or {}
    personamem_stats = stats.get("personamem_evidence") or {}
    retrieval_metrics = personamem_stats.get("retrieval_stage") or {}
    rerank_metrics = personamem_stats.get("rerank_stage") or {}
    answer_metrics = personamem_stats.get("answer_stage") or {}
    evidence_summary = personamem_stats.get("evidence_first_summary") or {}
    bucket_report = stats.get("bucket_report") or {}
    paired = results_data.get("paired_comparison") or {}
    statistical_confidence = paired.get("statistical_confidence") or {}
    primary_metrics = evidence_summary.get("primary_metrics") or {}
    diagnostic_labels = evidence_summary.get("diagnostic_labels") or []
    wrong_cases = [q for q in qa_results if q.get("is_correct") is False]
    false_positive_cases = [
        q for q in qa_results
        if (q.get("retrieval_stage") or {}).get("retrieval_hit_loose")
        and not (q.get("retrieval_stage") or {}).get("answerable_context_hit")
    ]
    top_wrong_cases = [
        q for q in wrong_cases
        if _rank_within((q.get("retrieval_stage") or {}).get("loose_rank_position"), 3)
    ]
    return "\n".join(
        [
            "# PersonaMem-v2 Analysis",
            "",
            "## Overall Summary",
            f"- Result file: `{source_name}`",
            f"- Questions: {stats.get('total_questions', len(qa_results))}",
            f"- Answerable context hit@k: {primary_metrics.get('answerable_context_hit_at_k', retrieval_metrics.get('answerable_context_hit_at_k', 0)):.2f}%",
            f"- Target preference hit@k: {primary_metrics.get('target_preference_hit_at_k', retrieval_metrics.get('target_preference_hit_at_k', 0)):.2f}%",
            f"- Answer-anchor hit@k: {primary_metrics.get('target_answer_anchor_hit_at_k', retrieval_metrics.get('target_answer_anchor_hit_at_k', 0)):.2f}%",
            f"- Wrong-neighbor substitution rate: {primary_metrics.get('wrong_neighbor_substitution_rate', retrieval_metrics.get('wrong_neighbor_substitution_rate', 0)):.2f}%",
            f"- Target-evidence-not-retrieved rate: {primary_metrics.get('target_evidence_not_retrieved_rate', retrieval_metrics.get('target_evidence_not_retrieved_rate', 0)):.2f}%",
            f"- Answer accuracy: {primary_metrics.get('accuracy', stats.get('accuracy', stats.get('answer_accuracy', 0))):.2f}%",
            f"- Loose recall@k: {retrieval_metrics.get('loose_recall_at_k', 0):.2f}%",
            *([f"- Diagnostic labels: {', '.join(f'`{label}`' for label in diagnostic_labels)}"] if diagnostic_labels else []),
            "",
            "## Loose Recall vs Answerable Evidence",
            f"- Loose-vs-answerable gap: {retrieval_metrics.get('loose_vs_answerable_gap', 0):.2f} percentage points.",
            "- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.",
            "",
            "## Target Evidence Top-K Analysis",
            *_topk_metric_lines(retrieval_metrics),
            *(
                ["", "### Rerank Stage", *_topk_metric_lines(rerank_metrics)]
                if rerank_metrics
                else []
            ),
            "",
            "## Answer Support Types",
            *_counter_md_lines(answer_metrics.get("answer_support_type_counts") or retrieval_metrics.get("answer_support_type_counts") or {}),
            "",
            "## Bucket Report",
            *_bucket_md_lines(bucket_report),
            "",
            "## Statistical Confidence",
            *_confidence_md_lines(statistical_confidence),
            "",
            "## False-Positive Retrieval Hits",
            *_case_md_lines(false_positive_cases[:8], include_generated=False),
            "",
            "## Top1/Top3 But Wrong",
            *_case_md_lines(top_wrong_cases[:8], include_generated=True),
            "",
            "## PersonaMem-Specific Risks",
            *_counter_md_lines(retrieval_metrics.get("retrieval_failure_subtype_counts") or {}),
            "",
            "## Representative Bad Cases",
            *_case_md_lines(wrong_cases[:10], include_generated=True),
            "",
            "## Recommended Next Actions",
            "- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.",
            "- Retrieval: prioritize answerable evidence over same-domain neighbor memories.",
            "- Rerank: compare target rank before and after rerank with the same evidence metrics.",
            "- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.",
        ]
    )


def _topk_metrics(
    *,
    k: int,
    loose_rank_position: int | None,
    preference_rank: int | None,
    snippet_rank: int | None,
    answer_anchor_rank: int | None,
    answerable_rank: int | None,
) -> dict[str, bool]:
    metrics: dict[str, bool] = {}
    for bucket in (*TOP_K_BUCKETS, k):
        label = "k" if bucket == k else str(bucket)
        metrics[f"loose_hit_at_{label}"] = _rank_within(loose_rank_position, bucket)
        metrics[f"target_preference_hit_at_{label}"] = _rank_within(preference_rank, bucket)
        metrics[f"target_snippet_hit_at_{label}"] = _rank_within(snippet_rank, bucket)
        metrics[f"target_answer_anchor_hit_at_{label}"] = _rank_within(answer_anchor_rank, bucket)
        metrics[f"answerable_context_hit_at_{label}"] = _rank_within(answerable_rank, bucket)
    return metrics


def _answerable_rank(
    *,
    preference_rank: int | None,
    snippet_rank: int | None,
    answer_anchor_rank: int | None,
    correct_answer: str,
    supporting_preference: str,
) -> int | None:
    if answer_anchor_rank is not None:
        return answer_anchor_rank
    if preference_rank is not None and not _is_negative_constraint(supporting_preference):
        return preference_rank
    if snippet_rank is not None and _token_count(correct_answer) <= 2:
        return snippet_rank
    return None


def _first_rank(contexts: list[str], target: str, *, mode: str) -> int | None:
    target_tokens = _informative_tokens(target)
    if not target_tokens:
        return None
    target_text = _normalize_text(target)
    for index, context in enumerate(contexts, start=1):
        if not context:
            continue
        if target_text and len(target_text) >= 8 and target_text in context:
            return index
        context_tokens = set(_informative_tokens(context))
        if not context_tokens:
            continue
        overlap = len(set(target_tokens) & context_tokens)
        if _is_token_hit(overlap, len(set(target_tokens)), mode=mode):
            return index
    return None


def _is_token_hit(overlap: int, target_size: int, *, mode: str) -> bool:
    if target_size <= 0:
        return False
    ratio = overlap / target_size
    if mode == "snippet":
        return overlap >= 5 and ratio >= 0.22
    if mode == "answer":
        return (overlap >= 2 and ratio >= 0.55) or (target_size == 1 and overlap == 1)
    return (overlap >= 2 and ratio >= 0.60) or (target_size <= 3 and overlap == target_size)


def _target_evidence_source(
    preference_rank: int | None,
    snippet_rank: int | None,
    answer_anchor_rank: int | None,
) -> str:
    sources = []
    if preference_rank is not None:
        sources.append("preference")
    if snippet_rank is not None:
        sources.append("snippet")
    if answer_anchor_rank is not None:
        sources.append("answer_anchor")
    if not sources:
        return "unknown"
    if len(sources) == 1:
        return sources[0]
    return "mixed"


def _same_domain_wrong_neighbor(
    question: str,
    correct_answer: str,
    supporting_preference: str,
    contexts: list[str],
) -> bool:
    if not contexts:
        return False
    target_tokens = set(_informative_tokens(" ".join([question, correct_answer, supporting_preference])))
    top_tokens = set(_informative_tokens(contexts[0]))
    return bool(target_tokens & top_tokens) and not _rank_within(
        _first_rank([_normalize_text(contexts[0])], correct_answer, mode="answer"),
        1,
    )


def _topk_metric_lines(metrics: dict[str, Any]) -> list[str]:
    if not metrics:
        return ["- No PersonaMem evidence metrics were recorded."]
    keys = [
        "target_preference_hit_at_1",
        "target_preference_hit_at_3",
        "target_preference_hit_at_5",
        "target_preference_hit_at_k",
        "target_answer_anchor_hit_at_1",
        "target_answer_anchor_hit_at_3",
        "target_answer_anchor_hit_at_5",
        "target_answer_anchor_hit_at_k",
        "answerable_context_hit_at_1",
        "answerable_context_hit_at_3",
        "answerable_context_hit_at_5",
        "answerable_context_hit_at_k",
    ]
    return [f"- `{key}`: {float(metrics.get(key, 0)):.2f}%" for key in keys]


def _counter_md_lines(counter: dict[str, Any]) -> list[str]:
    if not counter:
        return ["- No data."]
    return [f"- `{key}`: {value}" for key, value in counter.items()]


def _bucket_md_lines(bucket_report: dict[str, Any]) -> list[str]:
    if not bucket_report:
        return ["- No bucket report recorded."]
    lines = []
    for bucket, values in bucket_report.items():
        lines.append(
            f"- `{bucket}`: n={values.get('sample_count', 0)}, "
            f"evidence_hit={float(values.get('evidence_hit_rate', 0)):.2f}%, "
            f"anchor_hit={float(values.get('target_answer_anchor_hit_rate', 0)):.2f}%, "
            f"accuracy={float(values.get('answer_accuracy', 0)):.2f}%"
        )
    return lines


def _confidence_md_lines(confidence: dict[str, Any]) -> list[str]:
    if not confidence:
        return ["- No paired confidence statistics recorded."]
    lines = [f"- Method: {confidence.get('method')}"]
    for key in ("answer_paired_win_loss", "evidence_paired_win_loss"):
        item = confidence.get(key) or {}
        lines.append(
            f"- `{key}`: win={item.get('win')}, loss={item.get('loss')}, "
            f"delta={item.get('paired_delta')}, ci95={item.get('normal_approx_ci_95')}, "
            f"strength={item.get('decision_strength')}"
        )
    return lines


def _case_md_lines(cases: list[dict[str, Any]], *, include_generated: bool) -> list[str]:
    if not cases:
        return ["- No cases."]
    lines: list[str] = []
    for case in cases:
        retrieval_stage = case.get("retrieval_stage") or {}
        lines.append(
            "- "
            f"row={case.get('row_index')} | "
            f"question={_shorten(case.get('question'), 130)} | "
            f"gold={_shorten(case.get('standard_answer'), 90)} | "
            f"loose_rank={retrieval_stage.get('loose_rank_position')} | "
            f"answerable_rank={retrieval_stage.get('answerable_context_rank')} | "
            f"subtype={retrieval_stage.get('retrieval_failure_subtype')}"
        )
        if include_generated:
            lines.append(f"  - generated: {_shorten(case.get('generated_answer'), 160)}")
        contexts = case.get("retrieved_contexts") or []
        if contexts:
            lines.append(f"  - top1: {_shorten(contexts[0], 180)}")
    return lines


def _flatten_personamem_results(results_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in results_data.get("samples", []):
        for item in sample.get("qa_results", []):
            rows.append(dict(item))
    return rows


def _rank_within(rank: Any, k: int) -> bool:
    return isinstance(rank, int) and 1 <= rank <= k


def _normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _informative_tokens(text: Any) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_\-']*", _normalize_text(text))
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _token_count(text: Any) -> int:
    return len(_informative_tokens(text))


def _contains_any(text: str, terms: set[str]) -> bool:
    lowered = _normalize_text(text)
    return any(term in lowered for term in terms)


def _is_negative_constraint(text: str) -> bool:
    return _contains_any(text, _NEGATIVE_CONSTRAINT_TERMS)


def _has_distractor_leak(generated_answer: str | None, incorrect_answers: list[str]) -> bool:
    answer = _normalize_text(generated_answer)
    if not answer:
        return False
    for distractor in incorrect_answers:
        normalized = _normalize_text(distractor)
        if normalized and len(normalized) >= 4 and normalized in answer:
            return True
    return False


def _shorten(text: Any, limit: int) -> str:
    raw = str(text or "").replace("\n", " ").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3].rstrip() + "..."
