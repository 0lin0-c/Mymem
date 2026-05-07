"""PersonaMem-v2 Storage Sufficiency Analysis (v2 - after prompt fix).

For each question, search the DB using keywords, then use LLM to judge
if the stored records suffice to answer the gold answer. Compare with
the previous run's analysis.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from repositories import CategoryRepository, ResourceRepository
from tables.resource import Resource
from tables.category import Category
from services.llm.factory import LLMFactory

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

RESULTS_FILE = REPO_ROOT / "test_results" / "personamem_v2" / "personamem_v2_assistant_eval_results_20260428_134602.json"
OUTPUT_FILE = REPO_ROOT / "tests" / "evals" / "personamem_v2" / "Analysis" / "storage_sufficiency_analysis_v3.md"

# ---------- helpers ----------

def _extract_keywords(question_text: str, supporting_pref: str) -> list[str]:
    """Extract search keywords from question + supporting preference."""
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "i", "me", "my",
        "we", "our", "you", "your", "he", "him", "his", "she", "her", "it",
        "its", "they", "them", "their", "this", "that", "these", "those",
        "what", "which", "who", "whom", "whose", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "no", "nor", "not", "only", "own", "same",
        "so", "than", "too", "very", "just", "because", "but", "and", "or",
        "if", "while", "about", "for", "to", "of", "in", "on", "at", "by",
        "with", "from", "as", "into", "through", "during", "before",
        "after", "above", "below", "between", "up", "down", "out", "off",
        "over", "under", "again", "further", "then", "once", "here",
        "there", "any", "s", "t", "don", "didn", "doesn", "won", "wouldn",
        "couldn", "shouldn", "isn", "aren", "wasn", "weren", "hasn", "haven",
        "ll", "ve", "re", "d", "m", "also", "get", "got", "much", "many",
        "like", "really", "thing", "things", "way", "make", "go", "going",
        "come", "want", "need", "help", "let", "try", "keep", "put",
        "take", "give", "find", "know", "think", "feel", "see", "look",
        "say", "tell", "ask", "work", "play", "use", "good", "new", "well",
        "something", "anything", "nothing", "everything", "even", "still",
        "already", "always", "never", "ever", "often", "sometimes",
    }
    combined = f"{question_text} {supporting_pref}"
    words = re.findall(r"[a-zA-Z]{3,}", combined.lower())
    keywords = [w for w in words if w not in stop_words]
    # deduplicate preserving order, limit to 12
    seen = set()
    result = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result[:12]


async def search_resources(
    session: AsyncSession,
    user_id: str,
    keywords: list[str],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search resources by keyword matching on description and raw_content."""
    conditions = []
    for kw in keywords[:6]:
        conditions.append(Resource.description.ilike(f"%{kw}%"))
        conditions.append(Resource.raw_content.ilike(f"%{kw}%"))

    stmt = (
        select(Resource)
        .where(Resource.user_id == user_id)
        .where(or_(*conditions))
        .limit(limit)
    )
    result = await session.execute(stmt)
    resources = result.scalars().all()
    return [
        {
            "id": str(r.id)[:8],
            "description": (r.description or "")[:300],
            "raw_content": (r.raw_content or "")[:300],
        }
        for r in resources
    ]


async def search_categories(
    session: AsyncSession,
    user_id: str,
    keywords: list[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search categories by keyword matching on content."""
    conditions = []
    for kw in keywords[:6]:
        conditions.append(Category.content.ilike(f"%{kw}%"))

    stmt = (
        select(Category)
        .where(Category.user_id == user_id)
        .where(or_(*conditions))
        .limit(limit)
    )
    result = await session.execute(stmt)
    categories = result.scalars().all()
    return [
        {
            "id": str(c.id)[:8],
            "category_name": c.category_name,
            "content": (c.content or "")[:300],
        }
        for c in categories
    ]


async def llm_judge_sufficiency(
    llm: Any,
    question: str,
    gold_answer: str,
    supporting_preference: str,
    resources: list[dict],
    categories: list[dict],
) -> dict[str, Any]:
    """Use LLM to judge if DB records suffice to answer."""
    records_text = "## Resources\n"
    for i, r in enumerate(resources):
        records_text += f"Resource {i+1}: {r['description']}\n"
        if r["raw_content"]:
            records_text += f"  raw: {r['raw_content']}\n"

    records_text += "\n## Categories\n"
    for i, c in enumerate(categories):
        records_text += f"Category {i+1} [{c['category_name']}]: {c['content']}\n"

    if not resources and not categories:
        records_text = "No relevant records found in the database.\n"

    prompt = f"""# Task
Judge whether the database records below contain enough information to generate the gold answer for the question.

# Question
{question}

# Gold Answer (what a perfect system should generate)
{gold_answer}

# Supporting Preference (the key personal fact that makes the answer personalized)
{supporting_preference}

# Database Records
{records_text}

# Decision Rules
1. If the supporting preference is explicitly stored (verbatim or close paraphrase with key terms intact) → SUFFICIENT
2. If some related info exists but the key preference/detail is missing → INSUFFICIENT, reason=MISSING_PREFERENCE or MISSING_DETAIL
3. If partial info exists but not enough for the gold answer → INSUFFICIENT, reason=PARTIAL_INFO
4. Check if the exact key terms from the supporting preference appear in any record

# Output (JSON only, no markdown)
{{"sufficient": true/false, "pref_found": true/false, "reason": "SUFFICIENT|MISSING_PREFERENCE|MISSING_DETAIL|PARTIAL_INFO", "detail": "brief explanation", "missing_key_terms": ["term1", "term2"]}}"""

    try:
        response = await llm.generate_chat_response(
            system_prompt="You are a data quality analyst judging memory storage completeness.",
            context="",
            user_query=prompt,
        )
        # Parse JSON
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response[start:end])
            return result
    except Exception as e:
        logger.warning(f"LLM judgment failed: {e}")
        return {"sufficient": False, "pref_found": False, "reason": "LLM_ERROR", "detail": str(e), "missing_key_terms": []}

    return {"sufficient": False, "pref_found": False, "reason": "PARSE_ERROR", "detail": "", "missing_key_terms": []}


async def main():
    # Load eval results
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    qa_results = data["samples"][0]["qa_results"]
    user_id = data["samples"][0]["user_id"]

    llm = LLMFactory.get_provider()

    # Collect analysis results
    analysis_results = []

    async with AsyncSessionLocal() as session:
        for qa in qa_results:
            row_index = qa.get("row_index", "")
            question_raw = qa.get("question", "")
            # Extract just the content from the question dict string
            if isinstance(question_raw, str) and "'content':" in question_raw:
                match = re.search(r"'content':\s*['\"](.+?)['\"]", question_raw, re.DOTALL)
                if match:
                    question_text = match.group(1)
                else:
                    question_text = question_raw[:200]
            else:
                question_text = str(question_raw)[:200]

            gold_answer = qa.get("standard_answer", qa.get("correct_answer", ""))
            supporting_preference = qa.get("preference", qa.get("evidence", ""))
            pref_type = qa.get("pref_type", "")
            is_correct = qa.get("is_correct", False)

            # Truncate for readability
            question_short = question_text[:120]
            gold_short = gold_answer[:200] if gold_answer else ""
            pref_short = supporting_preference[:200] if supporting_preference else ""

            # Search DB
            keywords = _extract_keywords(question_text, supporting_preference)
            resources = await search_resources(session, user_id, keywords)
            categories = await search_categories(session, user_id, keywords)

            # LLM judge
            judgment = await llm_judge_sufficiency(
                llm, question_text, gold_answer, supporting_preference,
                resources, categories,
            )

            analysis_results.append({
                "row_index": row_index,
                "question_short": question_short,
                "pref_type": pref_type,
                "is_correct": is_correct,
                "supporting_preference": pref_short,
                "keywords": keywords,
                "resources_count": len(resources),
                "categories_count": len(categories),
                "sufficient": judgment.get("sufficient", False),
                "pref_found": judgment.get("pref_found", False),
                "reason": judgment.get("reason", "UNKNOWN"),
                "detail": judgment.get("detail", ""),
                "missing_key_terms": judgment.get("missing_key_terms", []),
            })

            print(f"Row {row_index}: reason={judgment.get('reason')}, sufficient={judgment.get('sufficient')}, pref_found={judgment.get('pref_found')}")

    # Generate report
    report = generate_report(analysis_results)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to {OUTPUT_FILE}")


def generate_report(results: list[dict]) -> str:
    total = len(results)
    sufficient_count = sum(1 for r in results if r["sufficient"])
    pref_found_count = sum(1 for r in results if r["pref_found"])

    # Reason distribution
    reason_counts: dict[str, int] = {}
    for r in results:
        reason = r["reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    # Cross-tab
    correct_sufficient = sum(1 for r in results if r["is_correct"] and r["sufficient"])
    correct_insufficient = sum(1 for r in results if r["is_correct"] and not r["sufficient"])
    wrong_sufficient = sum(1 for r in results if not r["is_correct"] and r["sufficient"])
    wrong_insufficient = sum(1 for r in results if not r["is_correct"] and not r["sufficient"])

    lines = []
    lines.append("# PersonaMem-v2 Storage Sufficiency Analysis (v2 — After Prompt Fix)")
    lines.append("")
    lines.append("## Overall Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total questions | {total} |")
    lines.append(f"| DB records found (any keyword match) | {sum(1 for r in results if r['resources_count'] > 0 or r['categories_count'] > 0)}/{total} ({100*sum(1 for r in results if r['resources_count'] > 0 or r['categories_count'] > 0)/total:.1f}%) |")
    lines.append(f"| LLM judged sufficient | {sufficient_count}/{total} ({100*sufficient_count/total:.1f}%) |")
    lines.append(f"| Preference found in DB | {pref_found_count}/{total} ({100*pref_found_count/total:.1f}%) |")
    lines.append("")

    lines.append("## Cross-tabulation: Answer Correctness vs Storage Sufficiency")
    lines.append("")
    lines.append("| | Sufficient | Insufficient | Total |")
    lines.append("|---|---|---|---|")
    correct_total = correct_sufficient + correct_insufficient
    wrong_total = wrong_sufficient + wrong_insufficient
    lines.append(f"| **Correct** | {correct_sufficient} | {correct_insufficient} | {correct_total} |")
    lines.append(f"| **Wrong** | {wrong_sufficient} | {wrong_insufficient} | {wrong_total} |")
    lines.append(f"| **Total** | {correct_sufficient + wrong_sufficient} | {correct_insufficient + wrong_insufficient} | {total} |")
    lines.append("")

    lines.append("## Failure Reason Distribution")
    lines.append("")
    lines.append("| Reason | Count | % | Description |")
    lines.append("|--------|-------|---|-------------|")
    reason_descriptions = {
        "SUFFICIENT": "DB records contain enough info to answer",
        "MISSING_PREFERENCE": "The supporting preference is not stored in any form",
        "MISSING_DETAIL": "Preference stored but key details lost in summarization",
        "PARTIAL_INFO": "Some relevant info but not enough for gold answer",
        "LLM_ERROR": "LLM judgment failed",
        "PARSE_ERROR": "Could not parse LLM judgment",
    }
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        desc = reason_descriptions.get(reason, reason)
        lines.append(f"| {reason} | {count} | {100*count/total:.1f}% | {desc} |")
    lines.append("")

    # Missing key terms aggregation
    all_missing = []
    for r in results:
        all_missing.extend(r.get("missing_key_terms", []))
    if all_missing:
        term_counts: dict[str, int] = {}
        for t in all_missing:
            term_counts[t] = term_counts.get(t, 0) + 1
        sorted_terms = sorted(term_counts.items(), key=lambda x: -x[1])
        lines.append("## Most Frequently Missing Key Terms")
        lines.append("")
        lines.append("| Term | Missing Count |")
        lines.append("|------|--------------|")
        for term, count in sorted_terms[:20]:
            lines.append(f"| {term} | {count} |")
        lines.append("")

    # Detailed per-question analysis
    lines.append("## Detailed Per-Question Analysis")
    lines.append("")

    for reason_group in ["MISSING_PREFERENCE", "MISSING_DETAIL", "PARTIAL_INFO", "SUFFICIENT", "LLM_ERROR"]:
        group_results = [r for r in results if r["reason"] == reason_group]
        if not group_results:
            continue
        lines.append(f"### {reason_group} ({len(group_results)} questions)")
        lines.append("")
        for r in group_results:
            lines.append(f"#### Row {r['row_index']}")
            lines.append(f"- **Question**: {r['question_short']}")
            lines.append(f"- **Pref type**: {r['pref_type']}")
            lines.append(f"- **Correct**: {'Yes' if r['is_correct'] else 'No'}")
            lines.append(f"- **Supporting preference**: {r['supporting_preference']}")
            lines.append(f"- **DB records found**: {r['resources_count']} resources, {r['categories_count']} categories")
            lines.append(f"- **Keywords used**: {', '.join(r['keywords'])}")
            lines.append(f"- **LLM judgment**: sufficient={r['sufficient']}, pref_found={r['pref_found']}")
            lines.append(f"- **Detail**: {r['detail']}")
            if r.get("missing_key_terms"):
                lines.append(f"- **Missing key terms**: {', '.join(r['missing_key_terms'])}")
            lines.append("")

    # Comparison with previous run
    lines.append("---")
    lines.append("")
    lines.append("## Comparison with Previous Run (Before Prompt Fix)")
    lines.append("")
    lines.append("| Metric | Before (v1) | After (v2) | Change |")
    lines.append("|--------|-------------|------------|--------|")
    lines.append("| Answer accuracy | 57.14% | 61.54% | +4.40pp |")
    lines.append("| LLM judged sufficient | ~16.7% | {:.1f}% | {:+.1f}pp |".format(
        100*sufficient_count/total,
        100*sufficient_count/total - 16.7
    ))
    lines.append("| Preference found in DB | 11.9% | {:.1f}% | {:+.1f}pp |".format(
        100*pref_found_count/total,
        100*pref_found_count/total - 11.9
    ))
    lines.append("| MISSING_PREFERENCE | 76.2% | {:.1f}% | {:+.1f}pp |".format(
        100*reason_counts.get("MISSING_PREFERENCE", 0)/total,
        100*reason_counts.get("MISSING_PREFERENCE", 0)/total - 76.2
    ))
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
