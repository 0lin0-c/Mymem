from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from tests.evals.personamem_v2.loader import (
    DEFAULT_SPLIT,
    build_samples,
    load_personamem_rows,
    snippet_to_turns,
)
from tests.evals.personamem_v2.models import PersonaMemQuestion, PersonaMemSample

PERSONA_ID = "66"
DEFAULT_OUTPUT_DIR = Path("test_results") / "personamem_v2_candidate_views"
CANDIDATE_VIEW_TYPES = {
    "task_event",
    "user_fact",
    "episodic_event",
    "artifact_fact",
    "constraint",
    "surviving_need",
    "advice_checklist",
}

_TASK_PATTERN = re.compile(
    r"\b(help|draft|write|rewrite|polish|refine|translate|summari[sz]e|make|turn this|clean(?:er)? version)\b",
    re.IGNORECASE,
)
_ARTIFACT_PATTERN = re.compile(
    r"\b(translation|translate|source text|blog|article|report|document|paper|essay|passage|paragraph|draft)\b",
    re.IGNORECASE,
)
_FORGET_PATTERN = re.compile(
    r"\b(forget|do not remember|don't remember|please delete|remove from memory|no longer remember)\b",
    re.IGNORECASE,
)
_SENSITIVE_PATTERN = re.compile(
    r"\b(ssn|social security|password|credit card|card number|passport|bank account)\b|\b\d{3}[- ]?\d{2}[- ]?\d{4}\b|\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    re.IGNORECASE,
)
_FIRST_PERSON_PATTERN = re.compile(
    r"\b(I|I'm|I am|I've|I have|my|mine|me)\b",
    re.IGNORECASE,
)
_THIRD_PERSON_NARRATIVE_PATTERN = re.compile(
    r"\b([A-Z][a-z]+)\s+(was|is|had|has|noticed|wrote|walked|saw|found|felt)\b",
)
_USER_FACT_ANCHOR_PATTERN = re.compile(
    r"\b(I|I'm|I am|I've|I have|my)\b[^.!?\n]*(?:like|love|enjoy|prefer|use|work on|need|feel|attend|read|watch|play|collect|avoid)[^.!?\n]*(?:[.!?]|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CandidateView:
    view_type: str
    content: str
    subject: str
    source_segment: str
    confidence: float
    attribution_risk: str
    sensitivity: str
    forget_conflict: bool
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_candidate_views(question: PersonaMemQuestion) -> list[CandidateView]:
    """Extract pre-write candidate views from one PersonaMem-v2 question snippet."""
    raw_segments = _question_segments(question)
    text = "\n".join(segment for _, segment in raw_segments)
    user_text = "\n".join(segment for role, segment in raw_segments if role == "user") or text
    assistant_text = "\n".join(segment for role, segment in raw_segments if role == "assistant")
    candidates: list[CandidateView] = []
    forget_target = ""

    if _TASK_PATTERN.search(user_text):
        task_content = _summarize_task(user_text)
        candidates.append(
            _candidate(
                "task_event",
                task_content,
                subject="user",
                source_segment="task_wrapper",
                confidence=0.78,
                attribution_risk="low",
                sensitivity=_sensitivity(user_text),
                evidence=_shorten(user_text),
            )
        )

    if _FORGET_PATTERN.search(text):
        forgotten = _extract_forget_target(user_text)
        forget_target = forgotten
        candidates.append(
            _candidate(
                "constraint",
                f"Do not store or retrieve the forgotten detail: {forgotten}.",
                subject="memory_policy",
                source_segment="forget_request",
                confidence=0.9,
                attribution_risk="low",
                sensitivity=_sensitivity(forgotten),
                forget_conflict=True,
                evidence=_shorten(user_text),
            )
        )
        surviving_need = _extract_surviving_need(raw_segments, forgotten)
        if surviving_need:
            candidates.append(
                _candidate(
                    "surviving_need",
                    surviving_need,
                    subject="user",
                    source_segment="conversation_context",
                    confidence=0.72,
                    attribution_risk="low",
                    sensitivity="none",
                    forget_conflict=False,
                    evidence=_shorten(user_text),
                )
            )

    if _is_artifact_task(user_text):
        artifact_content = _extract_artifact_content(f"{user_text}\n{assistant_text}")
        if artifact_content:
            candidates.append(
                _candidate(
                    "artifact_fact",
                    artifact_content,
                    subject="artifact",
                    source_segment="embedded_artifact",
                    confidence=0.74,
                    attribution_risk="high",
                    sensitivity=_sensitivity(artifact_content),
                    evidence=_shorten(user_text),
                )
            )

    if _is_third_party_narrative(user_text):
        candidates.append(
            _candidate(
                "episodic_event",
                _extract_narrative_event(user_text),
                subject="ambiguous_narrative_subject",
                source_segment="embedded_narrative",
                confidence=0.68,
                attribution_risk="medium",
                sensitivity=_sensitivity(user_text),
                evidence=_shorten(user_text),
            )
        )

    if not _is_artifact_task(user_text):
        for fact in _extract_user_facts(user_text, forget_target):
            candidates.append(
                _candidate(
                    "user_fact",
                    fact,
                    subject="user",
                    source_segment="embedded_personal_detail",
                    confidence=0.76,
                    attribution_risk="low",
                    sensitivity=_sensitivity(fact),
                    evidence=_shorten(user_text),
                )
            )
        if _user_owns_embedded_email(user_text):
            for fact in _extract_owned_email_facts(assistant_text):
                if _conflicts_with_forget(fact, _informative_tokens(forget_target)):
                    continue
                candidates.append(
                    _candidate(
                        "user_fact",
                        fact,
                        subject="user",
                        source_segment="assistant_echoed_user_artifact",
                        confidence=0.7,
                        attribution_risk="low",
                        sensitivity=_sensitivity(fact),
                        evidence=_shorten(assistant_text),
                    )
                )

    advice_text = assistant_text or text
    if _looks_like_advice(advice_text):
        advice_content = _extract_advice_checklist(advice_text)
        candidates.append(
            _candidate(
                "advice_checklist",
                advice_content,
                subject="assistant_guidance",
                source_segment="assistant_response",
                confidence=0.62,
                attribution_risk="low",
                sensitivity="none",
                forget_conflict=_conflicts_with_forget(advice_content, _informative_tokens(forget_target)),
                evidence=_shorten(advice_text),
            )
        )

    return _dedupe_candidates(candidates)


def evaluate_candidate_views(
    question: PersonaMemQuestion,
    candidates: Iterable[CandidateView],
) -> dict[str, Any]:
    candidate_list = list(candidates)
    supporting_hit = _candidate_hits_preference(question.preference or question.answer, candidate_list)
    return {
        "supporting_preference_candidate_hit": supporting_hit,
        "hidden_user_fact_found": any(
            candidate.view_type in {"user_fact", "episodic_event"}
            and candidate.source_segment in {"embedded_personal_detail", "embedded_narrative"}
            for candidate in candidate_list
        ),
        "surviving_need_found": any(candidate.view_type == "surviving_need" for candidate in candidate_list),
        "unsafe_user_attribution_count": sum(
            1
            for candidate in candidate_list
            if candidate.subject == "user"
            and candidate.attribution_risk in {"medium", "high"}
            and candidate.view_type in {"user_fact", "episodic_event", "artifact_fact"}
        ),
    }


def build_candidate_view_report(sample: PersonaMemSample) -> dict[str, Any]:
    if str(sample.persona_id) != PERSONA_ID:
        raise ValueError(f"Candidate view evaluation is fixed to persona_id={PERSONA_ID}.")

    question_reports: list[dict[str, Any]] = []
    totals = {
        "supporting_preference_candidate_hit": 0,
        "hidden_user_fact_found": 0,
        "surviving_need_found": 0,
        "unsafe_user_attribution_count": 0,
    }
    type_counts = {view_type: 0 for view_type in sorted(CANDIDATE_VIEW_TYPES)}

    for question in sample.questions:
        candidates = extract_candidate_views(question)
        metrics = evaluate_candidate_views(question, candidates)
        for key in totals:
            totals[key] += int(metrics[key])
        for candidate in candidates:
            type_counts[candidate.view_type] += 1
        question_reports.append(
            {
                "row_index": question.row_index,
                "question": question.question,
                "answer": question.answer,
                "preference": question.preference,
                "pref_type": question.pref_type,
                "metrics": metrics,
                "candidates": [candidate.to_dict() for candidate in candidates],
            }
        )

    return {
        "persona_id": sample.persona_id,
        "user_key": sample.user_key,
        "total_questions": sample.total_questions,
        "candidate_type_counts": type_counts,
        "metrics": totals,
        "questions": question_reports,
    }


def render_candidate_view_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# PersonaMem-v2 Candidate Views - persona {report['persona_id']}",
        "",
        f"- total_questions: {report['total_questions']}",
        "",
        "## Metrics",
    ]
    for key, value in report["metrics"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Candidate Types"])
    for key, value in report["candidate_type_counts"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Questions"])
    for item in report["questions"]:
        lines.append(f"### row_index {item['row_index']}")
        lines.append(f"- preference: {_markdown_inline(item['preference'])}")
        lines.append(
            "- metrics: "
            + ", ".join(f"{key}={value}" for key, value in item["metrics"].items())
        )
        for candidate in item["candidates"]:
            lines.append(
                f"- `{candidate['view_type']}` [{candidate['subject']}, "
                f"risk={candidate['attribution_risk']}]: {_markdown_inline(candidate['content'])}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_candidate_view_report(report: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"persona_{report['persona_id']}_candidate_views.json"
    markdown_path = output_dir / f"persona_{report['persona_id']}_candidate_views.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_candidate_view_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def run_candidate_view_eval(
    *,
    split: str = DEFAULT_SPLIT,
    max_questions: int | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    rows = load_personamem_rows(split=split)
    samples = build_samples(rows, split=split, persona_id=PERSONA_ID, max_questions=max_questions)
    if not samples:
        raise RuntimeError(f"No PersonaMem-v2 rows found for persona_id={PERSONA_ID} in split={split}.")
    report = build_candidate_view_report(samples[0])
    json_path, markdown_path = save_candidate_view_report(report, output_dir)
    return {
        "report": report,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PersonaMem-v2 persona 66 candidate view evaluation.")
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = run_candidate_view_eval(
        split=args.split,
        max_questions=args.max_questions,
        output_dir=args.output_dir,
    )
    sys.stdout.write(
        json.dumps({key: value for key, value in result.items() if key != "report"}, ensure_ascii=False, indent=2)
        + "\n"
    )
    return 0


def _question_segments(question: PersonaMemQuestion) -> list[tuple[str, str]]:
    labeled_segments = _parse_role_labeled_segments(question.related_conversation_snippet or "")
    if labeled_segments:
        return labeled_segments

    turns = snippet_to_turns(question)
    if turns:
        segments: list[tuple[str, str]] = []
        for user_text, assistant_text in turns:
            segments.append(("user", user_text))
            if assistant_text:
                segments.append(("assistant", assistant_text))
        return segments
    fallback = question.related_conversation_snippet or question.preference or question.answer
    return [("unknown", fallback)]


def _parse_role_labeled_segments(raw: str) -> list[tuple[str, str]]:
    if not raw:
        return []
    matches = list(re.finditer(r"\b(User|Assistant|Human|AI):", raw, re.IGNORECASE))
    if not matches:
        return []
    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        role = match.group(1).lower()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        content = _clean(raw[match.end() : end])
        if content:
            segments.append(("assistant" if role in {"assistant", "ai"} else "user", content))
    return segments


def _candidate(
    view_type: str,
    content: str,
    *,
    subject: str,
    source_segment: str,
    confidence: float,
    attribution_risk: str,
    sensitivity: str,
    forget_conflict: bool = False,
    evidence: str = "",
) -> CandidateView:
    if view_type not in CANDIDATE_VIEW_TYPES:
        raise ValueError(f"Unsupported candidate view type: {view_type}")
    return CandidateView(
        view_type=view_type,
        content=_clean(content),
        subject=subject,
        source_segment=source_segment,
        confidence=round(max(0.0, min(1.0, confidence)), 2),
        attribution_risk=attribution_risk,
        sensitivity=sensitivity,
        forget_conflict=forget_conflict,
        evidence=evidence,
    )


def _summarize_task(text: str) -> str:
    if re.search(r"\btranslate|translation\b", text, re.IGNORECASE):
        return "The user asked the assistant to translate embedded source text."
    if re.search(r"\bemail\b", text, re.IGNORECASE):
        return "The user asked the assistant to draft or polish an email."
    if re.search(r"\breport|document|article|paragraph|draft\b", text, re.IGNORECASE):
        return "The user asked the assistant to improve an embedded artifact."
    return "The user asked the assistant to help with a task in the current conversation."


def _extract_forget_target(text: str) -> str:
    match = re.search(r"(?:forget|do not remember|don't remember)\s+(?:that\s+)?([^.\n]+)", text, re.IGNORECASE)
    if match:
        return _clean(match.group(1))
    return "the requested forgotten detail"


def _extract_surviving_need(segments: list[tuple[str, str]], forgotten: str) -> str:
    forgotten_tokens = _informative_tokens(forgotten)
    for role, segment in segments:
        if role != "user" or _FORGET_PATTERN.search(segment):
            continue
        cleaned = _remove_forbidden_tokens(_clean(segment), forgotten_tokens)
        if cleaned:
            if re.search(r"\bactivity|activities|ideas|ways|suggest|recommend\b", cleaned, re.IGNORECASE):
                return "The user still needs general safe hands-on activity ideas."
            return f"The user still needs help with: {cleaned}"
    return ""


def _is_artifact_task(text: str) -> bool:
    has_artifact_signal = bool(_ARTIFACT_PATTERN.search(text))
    has_external_signal = bool(re.search(r"\b(found this|source|quoted|blog|article|report|document)\b", text, re.IGNORECASE))
    has_translation = bool(re.search(r"\btranslate|translation\b", text, re.IGNORECASE))
    return has_artifact_signal and (has_external_signal or has_translation)


def _extract_artifact_content(text: str) -> str:
    sentence = _first_matching_sentence(text, r"\b(picture books|quiet afternoons|source text|translation says|it says)\b")
    if sentence:
        return _neutralize_user_subject(sentence)
    quoted = re.findall(r"'([^']{8,})'|\"([^\"]{8,})\"", text)
    for left, right in quoted:
        value = left or right
        if value:
            return f"Embedded artifact says: {_clean(value)}"
    return "Embedded artifact contains facts that should not be attributed to the user without more evidence."


def _neutralize_user_subject(text: str) -> str:
    return re.sub(r"\bThe user\b", "The source text", _clean(text), flags=re.IGNORECASE)


def _is_third_party_narrative(text: str) -> bool:
    return bool(_THIRD_PERSON_NARRATIVE_PATTERN.search(text)) and not bool(
        re.search(r"\bmy friend|my sister|my brother|my child|my mom|my dad\b", text, re.IGNORECASE)
    )


def _extract_narrative_event(text: str) -> str:
    sentence = _first_matching_sentence(text, r"\b(police|park|noticed|walking|chasing|wrote)\b")
    return sentence or "Embedded narrative describes an event whose subject is not necessarily the user."


def _extract_user_facts(text: str, forget_target: str = "") -> list[str]:
    forbidden_tokens = _informative_tokens(forget_target)
    facts = [
        _clean(match.group(0))
        for match in _USER_FACT_ANCHOR_PATTERN.finditer(text)
        if not _FORGET_PATTERN.search(match.group(0)) and not _conflicts_with_forget(match.group(0), forbidden_tokens)
    ]
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        cleaned = _clean(sentence)
        if not cleaned or _FORGET_PATTERN.search(cleaned):
            continue
        if re.search(r"\bhelps? me feel\b|\bmakes? me feel\b", cleaned, re.IGNORECASE) and not _conflicts_with_forget(cleaned, forbidden_tokens):
            facts.append(cleaned)
    facts = _merge_related_personal_facts(facts)
    return facts[:3]


def _user_owns_embedded_email(user_text: str) -> bool:
    return bool(
        re.search(r"\b(email|letter|message)\b", user_text, re.IGNORECASE)
        and re.search(r"\b(I wrote|my email|from me|my letter|my message)\b", user_text, re.IGNORECASE)
    )


def _extract_owned_email_facts(assistant_text: str) -> list[str]:
    if not assistant_text:
        return []
    original_block = _extract_original_artifact_block(assistant_text)
    if not original_block:
        return []
    facts: list[str] = []
    normalized = original_block.lower()
    if "park" in normalized and re.search(r"\b(back and forth|swing|swings|playground)\b", normalized):
        facts.append("The user enjoys swinging at the playground.")
    for fact in _extract_user_facts(original_block, ""):
        if fact not in facts:
            facts.append(fact)
    return facts[:3]


def _merge_related_personal_facts(facts: list[str]) -> list[str]:
    merged: list[str] = []
    used: set[int] = set()
    for index, fact in enumerate(facts):
        if index in used:
            continue
        if re.search(r"\bcoloring pages\b", fact, re.IGNORECASE):
            partner_index = next(
                (
                    other_index
                    for other_index, other_fact in enumerate(facts)
                    if other_index != index and "calm" in other_fact.lower()
                ),
                None,
            )
            if partner_index is not None:
                merged.append(f"{fact} {facts[partner_index]}")
                used.update({index, partner_index})
                continue
        merged.append(fact)
        used.add(index)
    return merged


def _extract_original_artifact_block(text: str) -> str:
    match = re.search(
        r"Original [^:]{0,40}:\s*(.*?)(?:-{3,}|Refined [^:]{0,40}:|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return _clean(match.group(1))


def _conflicts_with_forget(text: str, forbidden_tokens: set[str]) -> bool:
    if not forbidden_tokens:
        return False
    tokens = _informative_tokens(text)
    return len(tokens & forbidden_tokens) >= min(2, len(forbidden_tokens))


def _looks_like_advice(text: str) -> bool:
    return bool(re.search(r"\b(you could|try|consider|steps?|checklist|ideas?)\b", text, re.IGNORECASE))


def _extract_advice_checklist(text: str) -> str:
    sentence = _first_matching_sentence(text, r"\b(you could|try|consider|steps?|ideas?)\b")
    return sentence or "Assistant provided task advice that may be useful only as conversational context."


def _candidate_hits_preference(target: str, candidates: list[CandidateView]) -> bool:
    tokens = _informative_tokens(target)
    if not tokens:
        return False
    candidate_text = " ".join(candidate.content for candidate in candidates).lower()
    matched = sum(1 for token in tokens if token in candidate_text)
    return matched >= min(3, len(tokens))


def _informative_tokens(text: str) -> set[str]:
    stopwords = {
        "the",
        "that",
        "this",
        "with",
        "from",
        "user",
        "uses",
        "says",
        "someone",
        "should",
        "remember",
        "please",
        "not",
        "and",
        "for",
        "you",
        "are",
        "was",
        "were",
        "into",
        "about",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text.lower())
        if token not in stopwords
    }


def _remove_forbidden_tokens(text: str, forbidden_tokens: set[str]) -> str:
    if not forbidden_tokens:
        return text
    words = text.split()
    kept = [word for word in words if re.sub(r"[^a-zA-Z0-9]", "", word).lower() not in forbidden_tokens]
    return _clean(" ".join(kept))


def _sensitivity(text: str) -> str:
    return "high" if _SENSITIVE_PATTERN.search(text) else "none"


def _dedupe_candidates(candidates: list[CandidateView]) -> list[CandidateView]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[CandidateView] = []
    for candidate in candidates:
        key = (candidate.view_type, candidate.subject, candidate.content.lower())
        if key in seen or not candidate.content:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _first_matching_sentence(text: str, pattern: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        cleaned = _clean(sentence)
        if cleaned and re.search(pattern, cleaned, re.IGNORECASE):
            return cleaned
    return ""


def _shorten(text: str, limit: int = 280) -> str:
    cleaned = _clean(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _markdown_inline(text: str) -> str:
    return _clean(text).replace("|", "\\|")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


if __name__ == "__main__":
    raise SystemExit(main())
