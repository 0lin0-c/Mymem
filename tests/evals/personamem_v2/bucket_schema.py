from __future__ import annotations

import re
from typing import Any


BUCKET_SCHEMA_VERSION = "personamem_v2_bucket_schema_v1"

BUCKET_DEFINITIONS: dict[str, dict[str, Any]] = {
    "exact_fact": {
        "description": "Question asks for a concrete fact, object, event, person, place, or action.",
        "evidence_source": "question/supporting_preference/snippet keyword mapping",
        "patterns": [r"\bwhat\b", r"\bwho\b", r"\bwhere\b", r"\bwhich\b", r"\bresearch(ed)?\b", r"\battend(ed)?\b"],
    },
    "broad_advice": {
        "description": "Question asks for advice, recommendations, steps, or checklist-like guidance.",
        "evidence_source": "question and answer intent keywords",
        "patterns": [r"\badvice\b", r"\btips?\b", r"\brecommend\b", r"\bsuggest\b", r"\bchecklist\b", r"\bhow\b"],
    },
    "negative_constraint": {
        "description": "Question or evidence contains a negation/avoidance constraint.",
        "evidence_source": "question/supporting_preference/stage subtype",
        "patterns": [r"\bavoid\b", r"\bwithout\b", r"\bnot\b", r"\bnever\b", r"\bno longer\b"],
    },
    "sensitive_info": {
        "description": "Question/evidence involves credentials, addresses, IDs, cards, health, email, or phone numbers.",
        "evidence_source": "PII/security keyword mapping",
        "patterns": [r"\bcredit card\b", r"\baddress\b", r"\bemail\b", r"\bphone\b", r"\bid\b", r"\bhealth\b", r"\bmedical\b", r"\bpassword\b"],
    },
    "third_person_narrative": {
        "description": "Relevant memory is embedded in a third-person or named narrative.",
        "evidence_source": "snippet/narrative attribution keywords",
        "patterns": [r"\bstory\b", r"\bnarrative\b", r"\babout [A-Z][a-z]+\b", r"\b[A-Z][a-z]+ said\b"],
    },
    "quoted_artifact": {
        "description": "Relevant fact is inside quoted, drafted, translated, or polished user-provided text.",
        "evidence_source": "quoted text/editing task keywords",
        "patterns": [r"\".{8,}\"", r"'.{8,}'", r"\bemail\b", r"\bdraft\b", r"\btranslate\b", r"\bpolish\b", r"\bsound better\b"],
    },
    "forget_request": {
        "description": "Question/evidence involves an explicit request to forget or retract a memory.",
        "evidence_source": "forget/retraction keywords",
        "patterns": [r"\bforget\b", r"\bdo not remember\b", r"\bdon't remember\b", r"\bdelete\b", r"\bremove\b", r"\bretract\b"],
    },
    "time_date_question": {
        "description": "Question asks for a date, time, ordering, or temporal occurrence.",
        "evidence_source": "temporal question keywords",
        "patterns": [r"\bwhen\b", r"\bdate\b", r"\btime\b", r"\byear\b", r"\bmonth\b", r"\byesterday\b", r"\btoday\b"],
    },
}


def classify_with_bucket_schema(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    text = " ".join(
        str(item.get(key) or "")
        for key in (
            "question",
            "standard_answer",
            "correct_answer",
            "supporting_preference",
            "related_conversation_snippet",
        )
    )
    stage = item.get("retrieval_stage") or {}
    subtype = str(stage.get("answer_support_subtype") or stage.get("answer_support_type") or "")
    if subtype == "negative_constraint_only":
        return "negative_constraint", _source("negative_constraint", ["stage:negative_constraint_only"])

    matches: dict[str, list[str]] = {}
    for bucket, definition in BUCKET_DEFINITIONS.items():
        for pattern in definition["patterns"]:
            if re.search(pattern, text, re.I):
                matches.setdefault(bucket, []).append(pattern)

    priority = [
        "forget_request",
        "sensitive_info",
        "negative_constraint",
        "quoted_artifact",
        "third_person_narrative",
        "time_date_question",
        "broad_advice",
        "exact_fact",
    ]
    for bucket in priority:
        if bucket in matches:
            return bucket, _source(bucket, matches[bucket])
    return "exact_fact", _source("exact_fact", ["default_exact_fact"])


def bucket_schema_payload() -> dict[str, Any]:
    return {
        "version": BUCKET_SCHEMA_VERSION,
        "buckets": BUCKET_DEFINITIONS,
        "priority": [
            "forget_request",
            "sensitive_info",
            "negative_constraint",
            "quoted_artifact",
            "third_person_narrative",
            "time_date_question",
            "broad_advice",
            "exact_fact",
        ],
    }


def _source(bucket: str, patterns: list[str]) -> dict[str, Any]:
    definition = BUCKET_DEFINITIONS[bucket]
    return {
        "bucket_schema_version": BUCKET_SCHEMA_VERSION,
        "bucket": bucket,
        "evidence_source": definition["evidence_source"],
        "matched_patterns": patterns,
    }
