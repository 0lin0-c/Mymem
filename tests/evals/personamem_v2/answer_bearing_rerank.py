from __future__ import annotations

import re
from typing import Any


_STOPWORDS = {
    "about",
    "after",
    "again",
    "answer",
    "because",
    "before",
    "could",
    "does",
    "from",
    "have",
    "into",
    "like",
    "more",
    "most",
    "need",
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
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}

_SLOT_TERMS = {
    "who": {"person", "friend", "mother", "father", "teacher", "doctor", "neighbor", "colleague"},
    "where": {"at", "in", "near", "from", "location", "place", "address", "city", "school"},
    "when": {"on", "in", "during", "after", "before", "date", "year", "month", "week", "yesterday", "today"},
    "what": {"made", "researched", "attended", "asked", "likes", "prefers", "means", "stands", "represents"},
    "how": {"steps", "checklist", "advice", "strategy", "method", "way", "securely", "safely"},
}

_NEGATIVE_TERMS_RE = re.compile(
    r"\b(forget|forgot|do not remember|don't remember|delete|remove|retract|avoid|without|not|never|no longer)\b",
    re.I,
)


def classify_answer_bearing_need(question: str) -> dict[str, Any]:
    lowered = str(question or "").lower()
    slots = [
        slot
        for slot in _SLOT_TERMS
        if slot in lowered or (slot == "when" and any(term in lowered for term in ("date", "time", "year")))
    ]
    if any(term in lowered for term in ("advice", "recommend", "tips", "how", "securely", "safely")):
        query_type = "advice_checklist"
    elif any(term in lowered for term in ("when", "where", "who", "what", "which", "date", "time")):
        query_type = "exact_fact"
    else:
        query_type = "profile_or_preference"
    return {
        "query_type": query_type,
        "required_slots": slots,
        "negative_or_forget_sensitive": bool(_NEGATIVE_TERMS_RE.search(lowered)),
    }


def rerank_answer_bearing_contexts(
    *,
    question: str,
    contexts: list[str],
    scores: list[float] | None = None,
    top_n: int | None = None,
) -> tuple[list[str], list[float], dict[str, Any]]:
    base_scores = list(scores or [])
    need = classify_answer_bearing_need(question)
    scored = []
    for index, context in enumerate(contexts):
        original_score = float(base_scores[index]) if index < len(base_scores) else 0.0
        features = score_answer_bearing_context(question=question, context=context)
        combined = _combined_score(features, original_score, need)
        scored.append(
            {
                "index": index,
                "context": context,
                "original_score": original_score,
                "answer_bearing_score": round(combined, 6),
                "features": features,
            }
        )
    scored.sort(key=lambda item: (-item["answer_bearing_score"], item["index"]))
    if top_n is not None:
        scored = scored[:top_n]
    return (
        [item["context"] for item in scored],
        [item["answer_bearing_score"] for item in scored],
        {
            "type": "answer_bearing",
            "need": need,
            "scored_candidates": scored,
            "top_n": top_n,
        },
    )


def score_answer_bearing_context(*, question: str, context: str) -> dict[str, float]:
    question_tokens = set(_tokens(question))
    context_tokens = set(_tokens(context))
    overlap = len(question_tokens & context_tokens)
    query_token_overlap = overlap / len(question_tokens) if question_tokens else 0.0
    slot_coverage = _slot_coverage(question, context)
    specificity_score = _specificity_score(context)
    negative_constraint = 1.0 if _NEGATIVE_TERMS_RE.search(str(context or "")) else 0.0
    positive_answer_signal = 1.0 if _has_positive_answer_signal(question, context) else 0.0
    return {
        "query_token_overlap": round(query_token_overlap, 6),
        "slot_coverage": round(slot_coverage, 6),
        "specificity_score": round(specificity_score, 6),
        "negative_constraint": negative_constraint,
        "positive_answer_signal": positive_answer_signal,
    }


def apply_answer_bearing_result_policy(
    *,
    question: str,
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    need = classify_answer_bearing_need(question)
    adjusted: list[dict[str, Any]] = []
    positive_evidence_count = 0
    negative_only_count = 0

    for index, result in enumerate(results):
        text = _result_text(result)
        features = score_answer_bearing_context(question=question, context=text)
        original_score = float(result.get("score", 0) or 0)
        adjusted_score = _combined_score(features, original_score, need)

        if features["positive_answer_signal"] > 0:
            positive_evidence_count += 1
        if features["negative_constraint"] > 0 and features["positive_answer_signal"] <= 0:
            negative_only_count += 1
            if need["negative_or_forget_sensitive"]:
                adjusted_score *= 0.82

        marked = dict(result)
        marked["score"] = adjusted_score
        marked["answer_bearing_trace"] = {
            "original_score": original_score,
            "adjusted_score": adjusted_score,
            "features": features,
            "need": need,
            "original_rank": index + 1,
        }
        if need["negative_or_forget_sensitive"] and features["negative_constraint"] > 0:
            marked["negative_constraint_candidate"] = True
        adjusted.append(marked)

    adjusted.sort(key=lambda item: (-float(item.get("score", 0) or 0), item["answer_bearing_trace"]["original_rank"]))
    trace = {
        "type": "answer_bearing_retrieval_policy",
        "need": need,
        "positive_evidence_count": positive_evidence_count,
        "negative_only_count": negative_only_count,
        "negative_constraint_only_context": positive_evidence_count == 0 and negative_only_count > 0,
    }
    return adjusted, trace


def _combined_score(features: dict[str, float], original_score: float, need: dict[str, Any]) -> float:
    combined = (
        features["query_token_overlap"] * 0.18
        + features["slot_coverage"] * 0.12
        + features["specificity_score"] * 0.08
        + features["positive_answer_signal"] * 0.22
        + min(max(original_score, 0.0), 1.0)
    )
    if need["negative_or_forget_sensitive"] and features["negative_constraint"] > 0:
        combined += 0.03
    return round(combined, 6)


def _slot_coverage(question: str, context: str) -> float:
    need = classify_answer_bearing_need(question)
    context_tokens = set(_tokens(context))
    expected_slots = need["required_slots"]
    if not expected_slots:
        return 0.0
    hits = 0
    for slot in expected_slots:
        if context_tokens & _SLOT_TERMS[slot]:
            hits += 1
    return hits / len(expected_slots)


def _specificity_score(context: str) -> float:
    raw = str(context or "")
    tokens = _tokens(raw)
    if not tokens:
        return 0.0
    named_like = len(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", raw))
    numbers = len(re.findall(r"\b\d{2,4}\b", raw))
    quoted = 1 if re.search(r"['\"].+?['\"]", raw) else 0
    concrete = min(len(tokens) / 18.0, 1.0)
    return min(concrete + 0.15 * named_like + 0.15 * numbers + 0.1 * quoted, 1.5)


def _has_positive_answer_signal(question: str, context: str) -> bool:
    features = classify_answer_bearing_need(question)
    text = str(context or "")
    if features["negative_or_forget_sensitive"] and _NEGATIVE_TERMS_RE.search(text):
        if not re.search(r"\b(should|try|use|check|make sure|steps?|recommend|protect|secure|safe|instead|alternative)\b", text, re.I):
            return False
    if features["query_type"] == "advice_checklist":
        return bool(re.search(r"\b(should|try|use|check|make sure|steps?|recommend|protect|secure|safe)\b", text, re.I))
    if features["required_slots"]:
        return _slot_coverage(question, text) > 0
    return bool(set(_tokens(question)) & set(_tokens(text)))


def _result_text(result: dict[str, Any]) -> str:
    category = result.get("category")
    resource = result.get("resource")
    parts = []
    if category is not None:
        parts.append(str(getattr(category, "content", "") or ""))
        parts.append(str(getattr(category, "category_name", "") or ""))
    if resource is not None:
        parts.append(str(getattr(resource, "description", "") or ""))
        parts.append(str(getattr(resource, "raw_content", "") or ""))
        parts.append(str(getattr(resource, "assistant_response", "") or ""))
    return "\n".join(part for part in parts if part)


def _tokens(text: Any) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_\-']*", str(text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]
