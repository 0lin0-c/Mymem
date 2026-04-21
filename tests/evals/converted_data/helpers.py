from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def parse_session_date(date_str: str) -> str | None:
    """Parse converted-data session dates into a stable DB-friendly string."""
    try:
        dt = datetime.strptime(date_str, "%I:%M %p on %d %B, %Y")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def parse_session_datetime(date_str: str) -> datetime | None:
    """Parse converted-data session dates into timezone-aware UTC datetimes."""
    parsed = parse_session_date(date_str)
    if not parsed:
        return None
    return datetime.strptime(parsed, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def extract_keywords(
    question: str,
    standard_answer: str,
    evidence: list[str],
    limit: int = 8,
) -> list[str]:
    """Extract rule-based DB diagnostic keywords from QA fields."""
    candidates: list[str] = []

    for src in [question, standard_answer, *evidence]:
        if not src:
            continue
        candidates.extend(re.findall(r"[\u4e00-\u9fff]{2,10}", src))
        candidates.extend(re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", src))

    stopwords = {
        "什么", "怎么", "是否", "为什么", "以及", "这个", "那个", "可以", "需要", "问题", "回答",
        "记忆", "系统", "用户", "助手", "please", "question", "answer",
    }
    seen = set()
    keywords = []
    for term in candidates:
        normalized = term.strip().lower()
        if len(normalized) < 2 or normalized in stopwords:
            continue
        if normalized not in seen:
            seen.add(normalized)
            keywords.append(normalized)
        if len(keywords) >= limit:
            break

    return keywords


def first_retrieved_rank(
    db_memories: list[dict[str, Any]],
    contexts: list[str],
) -> int | None:
    """Return a 1-based rank when a retrieved context contains a DB memory."""
    db_norms = [normalize_text(m.get("text", "")) for m in db_memories if m.get("text")]
    if not db_norms:
        return None

    for idx, context in enumerate(contexts, 1):
        ctx_norm = normalize_text(context)
        if any(mem_norm and mem_norm in ctx_norm for mem_norm in db_norms):
            return idx
    return None

