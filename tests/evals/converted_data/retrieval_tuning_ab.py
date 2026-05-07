from __future__ import annotations

import argparse
import asyncio
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from repositories import UserRepository
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever
from services.retrieval.scoring_config import (
    DEFAULT_RETRIEVAL_SCORING_CONFIG,
    RetrievalScoringConfig,
)
from tables import Category, Resource, User
from tests.evals.converted_data.helpers import first_retrieved_rank, normalize_text
from tests.evals.converted_data.loader import parse_qa_file
from tests.evals.converted_data.runner import _extract_retrieval_observation


REPO_ROOT = Path(__file__).parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "converted_data_recent_2026q1_name_trimmed"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "test_results" / "retrieval"


@dataclass(frozen=True)
class VariantSpec:
    name: str
    label: str
    top_k: int
    scoring_config: RetrievalScoringConfig


@dataclass(frozen=True)
class QuestionProbe:
    question: str
    anchors: tuple[str, ...]
    expected_answer: str | None = None


@dataclass
class EvidenceCandidate:
    id: str
    source: str
    category_name: str | None
    text: str
    matched_anchors: list[str]
    match_score: int
    importance_score: int | None
    updated_at: str | None


@dataclass
class FactorBreakdown:
    similarity: float
    access: float
    recency: float
    importance: float
    total: float


OLD_SCORING_CONFIG = RetrievalScoringConfig(
    recency_decay_days=60,
    similarity_power=1.5,
    access_power=1.0,
    recency_power=1.0,
    importance_power=1.0,
)


VARIANTS = (
    VariantSpec("A", "old_scoring_top5", 5, OLD_SCORING_CONFIG),
    VariantSpec("B", "new_scoring_top5", 5, DEFAULT_RETRIEVAL_SCORING_CONFIG),
    VariantSpec("C", "old_scoring_top10", 10, OLD_SCORING_CONFIG),
    VariantSpec("D", "new_scoring_top10", 10, DEFAULT_RETRIEVAL_SCORING_CONFIG),
)


TARGET_QUESTION_PROBES: dict[str, QuestionProbe] = {
    "When did Caroline go to the LGBTQ support group?": QuestionProbe(
        question="When did Caroline go to the LGBTQ support group?",
        expected_answer="4 January 2026",
        anchors=(
            "attended an LGBTQ support group yesterday (2026-01-04)",
            "attended an LGBTQ support group on 2026-01-04",
        ),
    ),
    "When did Caroline meet up with her friends, family, and mentors?": QuestionProbe(
        question="When did Caroline meet up with her friends, family, and mentors?",
        expected_answer="The week before 20 January 2026",
        anchors=(
            "shared a photo from a meetup with their support circle that took place around January 13, 2026",
            "meetup with their support circle that took place around January 13, 2026",
            "met up with their friends, family, and/or mentors around January 13, 2026 (last week)",
        ),
    ),
    "How long has Caroline had her current group of friends for?": QuestionProbe(
        question="How long has Caroline had her current group of friends for?",
        expected_answer="4 years",
        anchors=(
            "close group of friends they've known for 4 years",
            "group of friends they've known for 4 years",
        ),
    ),
    "Who supports Caroline when she has a negative experience?": QuestionProbe(
        question="Who supports Caroline when she has a negative experience?",
        expected_answer="Her mentors, family, and friends",
        anchors=(
            "friends, family, and mentors, describing them as their \"rocks\"",
            "support system—including friends, family, and mentors",
        ),
    ),
    "What workshop did Caroline attend recently?": QuestionProbe(
        question="What workshop did Caroline attend recently?",
        expected_answer="LGBTQ+ counseling workshop",
        anchors=(
            "attended an LGBTQ+ counseling workshop on Friday, January 23, 2026",
            "LGBTQ+ counseling workshop",
        ),
    ),
}


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_text(text: str | None, limit: int = 220) -> str:
    value = (text or "").replace("\n", " ").strip()
    return value[:limit]


def _days_ago(updated_at: datetime | None) -> float:
    if not updated_at:
        return 3650.0
    now = datetime.now(timezone.utc)
    dt = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    return max((now - dt).total_seconds() / 86400.0, 0.0)


def _vector_to_list(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            return [float(item.strip()) for item in stripped[1:-1].split(",") if item.strip()]
    return [float(item) for item in value]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(dot / (left_norm * right_norm), 0.0)


def _factor_breakdown(
    *,
    query_vector: list[float],
    description_vector: list[float] | None,
    access_count: int,
    updated_at: datetime | None,
    importance_score: int | None,
    scoring_config: RetrievalScoringConfig,
) -> FactorBreakdown:
    similarity = _cosine_similarity(query_vector, list(description_vector or []))
    similarity_factor = pow(max(similarity, 0.0), scoring_config.similarity_power)
    access_factor = pow(math.log(access_count + 2), scoring_config.access_power)
    recency_factor = pow(
        math.exp(-0.693 * _days_ago(updated_at) / scoring_config.recency_decay_days),
        scoring_config.recency_power,
    )
    importance_factor = pow(
        0.7 + ((importance_score or 0) / 10.0),
        scoring_config.importance_power,
    )
    return FactorBreakdown(
        similarity=similarity_factor,
        access=access_factor,
        recency=recency_factor,
        importance=importance_factor,
        total=similarity_factor * access_factor * recency_factor * importance_factor,
    )


def _classify_effect(results_by_variant: dict[str, dict[str, Any]]) -> str:
    a_hit = bool(results_by_variant["A"].get("retrieval_hit"))
    b_hit = bool(results_by_variant["B"].get("retrieval_hit"))
    c_hit = bool(results_by_variant["C"].get("retrieval_hit"))
    d_hit = bool(results_by_variant["D"].get("retrieval_hit"))
    shadow_hits = {
        name for name, payload in results_by_variant.items() if payload.get("shadow_resource_hit")
    }
    category_only_everywhere = all(
        payload.get("resolved_layer") == "category_only" for payload in results_by_variant.values()
    )

    if a_hit:
        return "neither helps"

    scoring_change = b_hit or (d_hit and not c_hit)
    top_k_change = c_hit or (d_hit and not b_hit)

    if scoring_change and top_k_change:
        return "both help"
    if scoring_change:
        return "scoring helps"
    if top_k_change:
        return "top_k helps"
    if category_only_everywhere and shadow_hits:
        return "tuning could help, but route stops at category_only"
    if category_only_everywhere:
        return "neither helps because route stops at category_only"
    return "neither helps"


async def _load_all_memory_texts(
    session: AsyncSession,
    user_id: str,
) -> tuple[list[Resource], list[Category]]:
    resources = (
        await session.execute(
            select(Resource)
            .where(Resource.user_id == user_id)
            .where(Resource.description.is_not(None))
        )
    ).scalars().all()
    categories = (
        await session.execute(select(Category).where(Category.user_id == user_id))
    ).scalars().all()
    return resources, categories


def _match_score(text: str, anchors: tuple[str, ...]) -> tuple[int, list[str]]:
    normalized_text = normalize_text(text)
    matched = [anchor for anchor in anchors if normalize_text(anchor) in normalized_text]
    return len(matched), matched


def _rank_candidates(
    resources: list[Resource],
    categories: list[Category],
    probe: QuestionProbe,
) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []

    for resource in resources:
        text = resource.description or resource.raw_content or ""
        score, matched = _match_score(text, probe.anchors)
        if score == 0:
            continue
        candidates.append(
            EvidenceCandidate(
                id=str(resource.id),
                source="resource",
                category_name=None,
                text=text,
                matched_anchors=matched,
                match_score=score,
                importance_score=resource.importance_score,
                updated_at=resource.updated_at.isoformat() if resource.updated_at else None,
            )
        )

    for category in categories:
        text = category.content or ""
        score, matched = _match_score(text, probe.anchors)
        if score == 0:
            continue
        candidates.append(
            EvidenceCandidate(
                id=str(category.id),
                source="category",
                category_name=category.category_name,
                text=text,
                matched_anchors=matched,
                match_score=score,
                importance_score=category.importance_score,
                updated_at=category.updated_at.isoformat() if category.updated_at else None,
            )
        )

    candidates.sort(
        key=lambda item: (
            item.match_score,
            1 if item.source == "resource" else 0,
            item.importance_score or 0,
            item.updated_at or "",
        ),
        reverse=True,
    )
    return candidates


async def _run_read_only_retrieval(
    retriever: MemoryRetriever,
    *,
    user_id: str,
    query: str,
    top_k: int,
    scoring_config: RetrievalScoringConfig,
) -> dict[str, Any]:
    categories = await retriever._classify_query(user_id, query)
    category_results = []
    if categories:
        category_results = await retriever._search_category_layer(
            user_id=user_id,
            categories=categories,
            query=query,
            top_k=top_k,
            scoring_config=scoring_config,
        )

    is_sufficient = await retriever._check_sufficiency(query, category_results)

    if is_sufficient:
        final_results = retriever._format_category_results(category_results)
    elif categories:
        resource_results = await retriever._search_resource_layer(
            user_id=user_id,
            categories=categories,
            query=query,
            top_k=top_k,
            scoring_config=scoring_config,
        )
        final_results = retriever._merge_results(category_results, resource_results)
    else:
        final_results = await retriever.vector_strategy.search(
            user_id=user_id,
            query=query,
            top_k=top_k,
            scoring_config=scoring_config,
        )

    final_results = retriever._deduplicate_and_rank(final_results)
    final_results = retriever._filter_by_threshold(final_results)
    final_results = final_results[:top_k]

    shadow_resource_results: list[dict[str, Any]] = []
    if categories:
        shadow_resource_results = await retriever._search_resource_layer(
            user_id=user_id,
            categories=categories,
            query=query,
            top_k=top_k,
            scoring_config=scoring_config,
        )
        shadow_resource_results = retriever._filter_by_threshold(
            retriever._deduplicate_and_rank(shadow_resource_results)
        )[:top_k]

    return {
        "categories": categories,
        "category_results": category_results,
        "is_sufficient": is_sufficient,
        "final_results": final_results,
        "shadow_resource_results": shadow_resource_results,
    }


async def _find_user_id(session: AsyncSession, username: str) -> str:
    repo = UserRepository(session)
    user = await repo.get_by_username(username)
    if not user:
        user = (
            await session.execute(select(User).where(User.username.ilike(username)))
        ).scalars().first()
    if not user:
        raise ValueError(f"User '{username}' not found in database.")
    return str(user.id)


def _top_contexts(results: list[dict[str, Any]], limit: int = 10) -> list[str]:
    contexts: list[str] = []
    for item in results[:limit]:
        resource = item.get("resource")
        category = item.get("category")
        if resource and resource.description:
            contexts.append(resource.description)
        elif category and category.content:
            contexts.append(category.content)
    return contexts


def _top_scores(results: list[dict[str, Any]], limit: int = 10) -> list[float]:
    return [round(float(item.get("score", 0.0)), 4) for item in results[:limit]]


def _matching_rank(
    candidates: list[EvidenceCandidate],
    contexts: list[str],
) -> int | None:
    probe_memories = [{"text": candidate.text} for candidate in candidates]
    return first_retrieved_rank(probe_memories, contexts)


def _find_resource_by_text(resources: list[Resource], candidate_text: str) -> Resource | None:
    candidate_norm = normalize_text(candidate_text)
    for resource in resources:
        if normalize_text(resource.description or resource.raw_content or "") == candidate_norm:
            return resource
    return None


def _variant_payload(
    *,
    final_results: list[dict[str, Any]],
    shadow_resource_results: list[dict[str, Any]],
    evidence_candidates: list[EvidenceCandidate],
) -> dict[str, Any]:
    contexts, scores, layer_info = _extract_retrieval_observation(final_results)
    shadow_contexts = _top_contexts(shadow_resource_results)
    return {
        "resolved_layer": layer_info.resolved_layer,
        "category_only": layer_info.resolved_layer == "category_only",
        "is_sufficient_at_category": layer_info.is_sufficient_at_category,
        "llm_classified_categories": layer_info.llm_classified_categories,
        "retrieval_hit": _matching_rank(evidence_candidates, contexts) is not None,
        "rank_position": _matching_rank(evidence_candidates, contexts),
        "top_contexts": contexts[:10],
        "top_scores": [round(float(score), 4) for score in scores[:10]],
        "shadow_resource_hit": _matching_rank(evidence_candidates, shadow_contexts) is not None,
        "shadow_resource_rank": _matching_rank(evidence_candidates, shadow_contexts),
        "shadow_top_contexts": shadow_contexts[:10],
        "shadow_top_scores": _top_scores(shadow_resource_results),
    }


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieval Tuning A/B Validation",
        "",
        f"- character: `{report['character']}`",
        f"- sample: `{report['sample_index']}`",
        f"- data_dir: `{report['data_dir']}`",
        f"- user_id: `{report['user_id']}`",
        f"- generated_at_utc: `{report['generated_at_utc']}`",
        "",
        "## Summary",
        "",
        f"- overall_judgement: `{report['summary']['overall_judgement']}`",
        f"- scoring_help_count: `{report['summary']['scoring_help_count']}`",
        f"- top_k_help_count: `{report['summary']['top_k_help_count']}`",
        f"- both_help_count: `{report['summary']['both_help_count']}`",
        f"- route_blocked_count: `{report['summary']['route_blocked_count']}`",
        f"- unresolved_count: `{report['summary']['unresolved_count']}`",
        "",
        "## Question Matrix",
        "",
        "| Question | Conclusion | A | B | C | D |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for item in report["questions"]:
        variant_cells = []
        for variant_name in ("A", "B", "C", "D"):
            variant = item["variants"][variant_name]
            cell = (
                f"{variant['resolved_layer']}"
                f"<br>hit={variant['retrieval_hit']}"
                f"<br>rank={variant['rank_position']}"
                f"<br>shadow={variant['shadow_resource_rank']}"
            )
            variant_cells.append(cell)
        lines.append(
            "| "
            + item["question"]
            + " | "
            + item["conclusion"]
            + " | "
            + " | ".join(variant_cells)
            + " |"
        )

    lines.extend(["", "## Per Question", ""])

    for item in report["questions"]:
        evidence = item["evidence_candidates"]
        top_evidence = evidence[0] if evidence else None
        lines.append(f"### {item['question']}")
        lines.append("")
        lines.append(f"- expected_answer: `{item['expected_answer']}`")
        lines.append(f"- conclusion: `{item['conclusion']}`")
        if top_evidence:
            lines.append(
                f"- db_evidence: `{top_evidence['source']}` | anchors={top_evidence['matched_anchors']} | text={top_evidence['text_preview']}"
            )
        else:
            lines.append("- db_evidence: `not_found_by_anchor_probe`")
        if item.get("factor_breakdown"):
            factor = item["factor_breakdown"]
            lines.append(
                "- target_factor_breakdown: "
                f"similarity={factor['target']['similarity']:.4f}, "
                f"access={factor['target']['access']:.4f}, "
                f"recency={factor['target']['recency']:.4f}, "
                f"importance={factor['target']['importance']:.4f}, "
                f"total={factor['target']['total']:.4f}"
            )
            if factor.get("shadow_top"):
                lines.append(
                    "- shadow_top_factor_breakdown: "
                    f"similarity={factor['shadow_top']['similarity']:.4f}, "
                    f"access={factor['shadow_top']['access']:.4f}, "
                    f"recency={factor['shadow_top']['recency']:.4f}, "
                    f"importance={factor['shadow_top']['importance']:.4f}, "
                    f"total={factor['shadow_top']['total']:.4f}"
                )
        lines.append("- variants:")
        for variant_name in ("A", "B", "C", "D"):
            variant = item["variants"][variant_name]
            lines.append(
                f"  - {variant_name}: layer={variant['resolved_layer']}, "
                f"hit={variant['retrieval_hit']}, rank={variant['rank_position']}, "
                f"shadow_rank={variant['shadow_resource_rank']}, "
                f"top1={_safe_text((variant['top_contexts'] or [''])[0] if variant['top_contexts'] else '')}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


async def run_analysis(
    *,
    sample_index: int = 0,
    data_dir: Path = DEFAULT_DATA_DIR,
    character: str = "caroline",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    qa_data = parse_qa_file(data_dir / f"sample_{sample_index}_qa.json")
    targets = [q for q in qa_data.questions if q.question in TARGET_QUESTION_PROBES]
    if not targets:
        raise ValueError("No target questions found in QA file.")

    async with AsyncSessionLocal() as session:
        user_id = await _find_user_id(session, character)
        llm = LLMFactory.get_provider()
        retriever = MemoryRetriever(session, llm)
        all_resources, all_categories = await _load_all_memory_texts(session, user_id)

        question_reports: list[dict[str, Any]] = []

        for qa in targets:
            probe = TARGET_QUESTION_PROBES[qa.question]
            evidence_candidates = _rank_candidates(all_resources, all_categories, probe)

            variants_payload: dict[str, dict[str, Any]] = {}
            raw_variant_runs: dict[str, dict[str, Any]] = {}
            for variant in VARIANTS:
                raw = await _run_read_only_retrieval(
                    retriever,
                    user_id=user_id,
                    query=qa.question,
                    top_k=variant.top_k,
                    scoring_config=variant.scoring_config,
                )
                raw_variant_runs[variant.name] = raw
                variants_payload[variant.name] = _variant_payload(
                    final_results=raw["final_results"],
                    shadow_resource_results=raw["shadow_resource_results"],
                    evidence_candidates=evidence_candidates,
                )

            factor_breakdown = None
            target_resource = None
            if evidence_candidates:
                for candidate in evidence_candidates:
                    if candidate.source == "resource":
                        target_resource = _find_resource_by_text(all_resources, candidate.text)
                        if target_resource:
                            break

            if target_resource:
                query_vector = await llm.get_embedding(qa.question)
                target_factor = _factor_breakdown(
                    query_vector=query_vector,
                    description_vector=_vector_to_list(target_resource.description_vector),
                    access_count=target_resource.access_count,
                    updated_at=target_resource.updated_at,
                    importance_score=target_resource.importance_score,
                    scoring_config=DEFAULT_RETRIEVAL_SCORING_CONFIG,
                )
                shadow_top_factor = None
                shadow_top = raw_variant_runs["D"]["shadow_resource_results"]
                if shadow_top:
                    top_resource = shadow_top[0].get("resource")
                    if top_resource and top_resource.description_vector is not None:
                        shadow_top_factor = _factor_breakdown(
                            query_vector=query_vector,
                            description_vector=_vector_to_list(top_resource.description_vector),
                            access_count=top_resource.access_count,
                            updated_at=top_resource.updated_at,
                            importance_score=top_resource.importance_score,
                            scoring_config=DEFAULT_RETRIEVAL_SCORING_CONFIG,
                        )
                factor_breakdown = {
                    "target": asdict(target_factor),
                    "shadow_top": asdict(shadow_top_factor) if shadow_top_factor else None,
                }

            conclusion = _classify_effect(variants_payload)
            question_reports.append(
                {
                    "question": qa.question,
                    "expected_answer": qa.answer,
                    "conclusion": conclusion,
                    "evidence": qa.evidence,
                    "evidence_candidates": [
                        {
                            **asdict(candidate),
                            "text_preview": _safe_text(candidate.text),
                        }
                        for candidate in evidence_candidates[:5]
                    ],
                    "variants": variants_payload,
                    "factor_breakdown": factor_breakdown,
                }
            )

    summary = {
        "scoring_help_count": sum(1 for item in question_reports if item["conclusion"] == "scoring helps"),
        "top_k_help_count": sum(1 for item in question_reports if item["conclusion"] == "top_k helps"),
        "both_help_count": sum(1 for item in question_reports if item["conclusion"] == "both help"),
        "route_blocked_count": sum(
            1
            for item in question_reports
            if item["conclusion"] in {
                "neither helps because route stops at category_only",
                "tuning could help, but route stops at category_only",
            }
        ),
        "unresolved_count": sum(1 for item in question_reports if item["conclusion"] == "neither helps"),
    }

    if summary["scoring_help_count"] or summary["top_k_help_count"] or summary["both_help_count"]:
        overall = "partial benefit"
    elif summary["route_blocked_count"] == len(question_reports):
        overall = "route bottleneck dominates"
    else:
        overall = "no demonstrated benefit"
    summary["overall_judgement"] = overall

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sample_index": sample_index,
        "character": character,
        "data_dir": str(data_dir),
        "user_id": user_id,
        "summary": summary,
        "questions": question_reports,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    json_path = output_dir / f"retrieval_tuning_ab_{stamp}.json"
    md_path = output_dir / f"retrieval_tuning_ab_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["markdown_path"] = str(md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="只读验证 retrieval scoring/top_k 调整是否改善特定 converted_data 问题。"
    )
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--character", type=str, default="caroline")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = asyncio.run(
        run_analysis(
            sample_index=args.sample,
            data_dir=args.data_dir,
            character=args.character,
            output_dir=args.output_dir,
        )
    )
    print(f"json_report={report['json_path']}")
    print(f"markdown_report={report['markdown_path']}")
    print(f"overall_judgement={report['summary']['overall_judgement']}")
    for item in report["questions"]:
        print(f"- {item['question']} => {item['conclusion']}")


if __name__ == "__main__":
    main()
