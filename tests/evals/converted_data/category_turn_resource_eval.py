from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever
from services.retrieval.scoring_config import DEFAULT_RETRIEVAL_SCORING_CONFIG
from tables import Category, Resource, ResourceCategory, User
from tests.evals.converted_data.loader import parse_qa_file
from tests.evals.converted_data.runner import (
    _extract_retrieval_observation,
    evaluate_answer_correctness,
    generate_answer_with_chat_orchestrator,
)


REPO_ROOT = Path(__file__).parents[3]
DEFAULT_QA_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "converted_data"
    / "unsupported_success_recheck"
    / "sample_0_qa.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "test_results" / "resource_audit"
DEFAULT_CACHE_PATH = REPO_ROOT / "test_results" / "cache" / "turnmemory_embedding_cache.json"


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


@dataclass
class TurnMemoryCandidate:
    resource: Resource
    text: str
    score: float
    similarity: float
    category_names: list[str]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"turnmemory": {}, "queries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("turnmemory", {})
    data.setdefault("queries", {})
    return data


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


async def _get_cached_embedding(
    llm: Any,
    cache: dict[str, Any],
    stats: CacheStats,
    *,
    namespace: str,
    key: str,
    text: str,
) -> list[float]:
    text_hash = _hash_text(text)
    cached = cache[namespace].get(key)
    if cached and cached.get("hash") == text_hash:
        stats.hits += 1
        return [float(value) for value in cached["embedding"]]
    stats.misses += 1
    embedding = await llm.get_embedding(text)
    cache[namespace][key] = {"hash": text_hash, "embedding": embedding}
    return embedding


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(dot / (left_norm * right_norm), 0.0)


def _days_ago(updated_at: datetime | None) -> float:
    if updated_at is None:
        return 3650.0
    dt = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - dt).total_seconds() / 86400.0, 0.0)


def _score_turnmemory(
    *,
    query_vector: list[float],
    turn_vector: list[float],
    resource: Resource,
) -> tuple[float, float]:
    config = DEFAULT_RETRIEVAL_SCORING_CONFIG
    similarity = _cosine_similarity(query_vector, turn_vector)
    similarity_factor = pow(similarity, config.similarity_power)
    access_factor = pow(math.log((resource.access_count or 0) + 2), config.access_power)
    recency_factor = pow(
        math.exp(-0.693 * _days_ago(resource.updated_at) / config.recency_decay_days),
        config.recency_power,
    )
    importance_factor = pow(0.7 + ((resource.importance_score or 0) / 10.0), config.importance_power)
    return similarity_factor * access_factor * recency_factor * importance_factor, similarity


async def _find_user(session: Any, username: str) -> User:
    user = (
        await session.execute(select(User).where(User.username.ilike(username)))
    ).scalars().first()
    if not user:
        raise ValueError(f"User '{username}' not found in database.")
    return user


async def _load_resources(session: Any, user_id: str) -> tuple[list[Resource], dict[str, list[str]]]:
    resources = (
        await session.execute(
            select(Resource)
            .where(Resource.user_id == user_id)
            .where(Resource.raw_content.is_not(None))
        )
    ).scalars().all()
    rows = (
        await session.execute(
            select(ResourceCategory.resource_id, Category.category_name)
            .join(Category, ResourceCategory.category_id == Category.id)
            .where(Category.user_id == user_id)
        )
    ).all()
    categories_by_resource: dict[str, list[str]] = {}
    for resource_id, category_name in rows:
        categories_by_resource.setdefault(str(resource_id), []).append(category_name)
    return list(resources), categories_by_resource


def _clone_resource(resource: Resource, description: str) -> Resource:
    return Resource(
        id=resource.id,
        user_id=resource.user_id,
        modality=resource.modality,
        raw_content=resource.raw_content,
        description=description,
        description_vector=resource.description_vector,
        importance_score=resource.importance_score,
        created_at=resource.created_at,
        assistant_response=resource.assistant_response,
        access_count=resource.access_count,
        updated_at=resource.updated_at,
    )


async def _rank_turnmemory(
    *,
    llm: Any,
    cache: dict[str, Any],
    cache_stats: CacheStats,
    query_vector: list[float],
    resources: list[Resource],
    categories_by_resource: dict[str, list[str]],
    allowed_categories: list[str] | None,
) -> list[TurnMemoryCandidate]:
    allowed = set(allowed_categories or [])
    candidates: list[TurnMemoryCandidate] = []
    for resource in resources:
        category_names = categories_by_resource.get(str(resource.id), [])
        if allowed and not (allowed & set(category_names)):
            continue
        text = (resource.raw_content or "").strip()
        if not text:
            continue
        turn_vector = await _get_cached_embedding(
            llm,
            cache,
            cache_stats,
            namespace="turnmemory",
            key=str(resource.id),
            text=text,
        )
        score, similarity = _score_turnmemory(
            query_vector=query_vector,
            turn_vector=turn_vector,
            resource=resource,
        )
        candidates.append(
            TurnMemoryCandidate(
                resource=resource,
                text=text,
                score=score,
                similarity=similarity,
                category_names=category_names,
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates


def _question_kind(question: str) -> str:
    q = question.lower()
    if any(token in q for token in ("likely", "identity", "political leaning", "fields would")):
        return "profile"
    if any(token in q for token in ("tell me about", "what has", "journey", "recently been up to")):
        return "broad"
    return "exact_fact"


def _format_category_results(
    retriever: MemoryRetriever,
    category_results: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    results = retriever._format_category_results(category_results)
    results = retriever._filter_by_threshold(retriever._deduplicate_and_rank(results))
    return results[:limit]


def _format_turn_results(candidates: list[TurnMemoryCandidate], limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for candidate in candidates[:limit]:
        results.append(
            {
                "resource": _clone_resource(candidate.resource, f"[TurnMemory] {candidate.text}"),
                "score": candidate.score,
                "strategy": "turnmemory_vector",
                "turnmemory_similarity": candidate.similarity,
                "turnmemory_category_names": candidate.category_names,
            }
        )
    return results


def _format_resource_expansions(
    candidates: list[TurnMemoryCandidate],
    *,
    limit: int,
    seen_resource_ids: set[str],
) -> list[dict[str, Any]]:
    expansions: list[dict[str, Any]] = []
    for candidate in candidates:
        resource_id = str(candidate.resource.id)
        if resource_id in seen_resource_ids:
            continue
        description = (candidate.resource.description or "").strip()
        if not description:
            continue
        seen_resource_ids.add(resource_id)
        expansions.append(
            {
                "resource": _clone_resource(candidate.resource, f"[ResourceSummary] {description}"),
                "score": candidate.score,
                "strategy": "resource_expansion",
                "expanded_from": "turnmemory",
            }
        )
        if len(expansions) >= limit:
            break
    return expansions


def _format_resource_summary_results(
    resource_results: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for result in resource_results[:limit]:
        resource = result.get("resource")
        if not resource or not resource.description:
            continue
        results.append(
            {
                "resource": _clone_resource(resource, f"[ResourceSummary] {resource.description}"),
                "score": result.get("score", 0.0),
                "strategy": "resource_vector",
            }
        )
    return results


def _dedupe_results(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for result in results:
        resource = result.get("resource")
        category = result.get("category")
        if category is not None:
            key = ("category", str(category.id))
        elif resource is not None:
            key = (result.get("strategy", "resource"), str(resource.id))
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
        if len(deduped) >= limit:
            break
    return deduped


def _top_score(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    return float(results[0].get("score", 0.0))


def _build_hybrid_results(
    *,
    question: str,
    category_results: list[dict[str, Any]],
    turn_candidates: list[TurnMemoryCandidate],
    resource_summary_results: list[dict[str, Any]],
    retriever: MemoryRetriever,
    top_k: int,
) -> list[dict[str, Any]]:
    kind = _question_kind(question)
    if kind == "profile":
        category_limit, turn_limit, expansion_limit, summary_limit = 8, 4, 2, 1
    elif kind == "broad":
        category_limit, turn_limit, expansion_limit, summary_limit = 4, 3, 2, 8
    else:
        category_limit, turn_limit, expansion_limit, summary_limit = 5, 8, 3, 2

    category_payload = _format_category_results(retriever, category_results, category_limit)
    turn_payload = _format_turn_results(turn_candidates, turn_limit)
    seen_expansion_ids = {
        str(result["resource"].id)
        for result in turn_payload
        if result.get("resource") is not None
    }
    expansion_payload = _format_resource_expansions(
        turn_candidates,
        limit=expansion_limit,
        seen_resource_ids=seen_expansion_ids,
    )
    summary_payload = _format_resource_summary_results(resource_summary_results, summary_limit)

    if kind == "profile":
        ordered = category_payload + turn_payload + expansion_payload + summary_payload
    elif kind == "broad":
        ordered = summary_payload + category_payload + turn_payload + expansion_payload
    else:
        ordered = category_payload + turn_payload + expansion_payload + summary_payload
    return _dedupe_results(ordered, top_k)


def _build_selective_results(
    *,
    question: str,
    category_payload: list[dict[str, Any]],
    turn_payload: list[dict[str, Any]],
    turn_candidates: list[TurnMemoryCandidate],
    resource_summary_results: list[dict[str, Any]],
    top_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pick one primary evidence grain instead of merging all grains blindly."""
    kind = _question_kind(question)
    top_category_score = _top_score(category_payload)
    top_turn_score = _top_score(turn_payload)
    top_turn_similarity = turn_candidates[0].similarity if turn_candidates else 0.0
    resource_payload = _format_resource_summary_results(resource_summary_results, top_k)

    selected = "category"
    reason = "profile_or_default_category_priority"

    if kind == "broad":
        if resource_payload:
            selected = "resource_summary"
            reason = "broad_question_resource_summary_priority"
            return resource_payload[:top_k], {
                "selected": selected,
                "reason": reason,
                "question_kind": kind,
                "top_category_score": round(top_category_score, 4),
                "top_turn_score": round(top_turn_score, 4),
                "top_turn_similarity": round(top_turn_similarity, 4),
            }
        reason = "broad_question_no_resource_summary_fallback"

    elif kind == "exact_fact":
        turn_is_competitive = (
            bool(turn_payload)
            and (
                not category_payload
                or top_turn_score >= top_category_score * 0.35
                or top_turn_similarity >= 0.27
            )
        )
        if turn_is_competitive:
            selected = "turnmemory"
            reason = "exact_fact_turnmemory_competitive"
            return turn_payload[:top_k], {
                "selected": selected,
                "reason": reason,
                "question_kind": kind,
                "top_category_score": round(top_category_score, 4),
                "top_turn_score": round(top_turn_score, 4),
                "top_turn_similarity": round(top_turn_similarity, 4),
            }
        reason = "exact_fact_category_stronger"

    if category_payload:
        results = category_payload[:top_k]
    elif turn_payload:
        selected = "turnmemory"
        reason = f"{kind}_no_category_fallback"
        results = turn_payload[:top_k]
    else:
        selected = "resource_summary"
        reason = f"{kind}_no_category_or_turnmemory_fallback"
        results = resource_payload[:top_k]

    return results, {
        "selected": selected,
        "reason": reason,
        "question_kind": kind,
        "top_category_score": round(top_category_score, 4),
        "top_turn_score": round(top_turn_score, 4),
        "top_turn_similarity": round(top_turn_similarity, 4),
    }


def _contexts_scores_and_strategies(results: list[dict[str, Any]]) -> tuple[list[str], list[float], list[str]]:
    contexts: list[str] = []
    scores: list[float] = []
    strategies: list[str] = []
    for result in results:
        resource = result.get("resource")
        category = result.get("category")
        if resource and resource.description:
            contexts.append(resource.description)
        elif category and category.content:
            contexts.append(category.content)
        else:
            continue
        scores.append(float(result.get("score", 0.0)))
        strategies.append(result.get("strategy", "unknown"))
    return contexts, scores, strategies


def _answer_anchor_hit(answer: str, contexts: list[str]) -> int | None:
    answer = (answer or "").strip().lower()
    if not answer:
        return None
    for index, context in enumerate(contexts, 1):
        if answer in (context or "").lower():
            return index
    return None


async def _answer_variant(
    *,
    session: Any,
    llm: Any,
    user: User,
    user_id: str,
    question: str,
    standard_answer: str,
    top_k: int,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    contexts, scores, strategies = _contexts_scores_and_strategies(results)
    started = time.perf_counter()
    answer = ""
    is_correct = False
    explanation = "No retrieved context available for assistant answer generation."
    if contexts:
        answer = await generate_answer_with_chat_orchestrator(
            session=session,
            llm=llm,
            user=user,
            user_id=user_id,
            question=question,
            top_k=top_k,
            retrieved_results=results,
        )
        is_correct, explanation = await evaluate_answer_correctness(
            llm,
            question,
            answer,
            standard_answer,
        )
    return {
        "is_correct": is_correct,
        "answer": answer,
        "explanation": explanation,
        "answer_anchor_rank": _answer_anchor_hit(standard_answer, contexts),
        "top_contexts": contexts[:5],
        "top_scores": [round(score, 4) for score in scores[:5]],
        "top_strategies": strategies[:5],
        "answer_seconds": round(time.perf_counter() - started, 3),
    }


async def _build_variant_inputs(
    *,
    retriever: MemoryRetriever,
    user_id: str,
    query: str,
    top_k: int,
    classified_categories: list[str],
    turn_candidates: list[TurnMemoryCandidate],
) -> dict[str, Any]:
    category_results = []
    resource_results = []
    if classified_categories:
        category_results = await retriever._search_category_layer(
            user_id=user_id,
            categories=classified_categories,
            query=query,
            top_k=top_k,
            scoring_config=DEFAULT_RETRIEVAL_SCORING_CONFIG,
        )
        resource_results = await retriever._search_resource_layer(
            user_id=user_id,
            categories=classified_categories,
            query=query,
            top_k=top_k,
            scoring_config=DEFAULT_RETRIEVAL_SCORING_CONFIG,
        )

    category_only = _format_category_results(retriever, category_results, top_k)
    turnmemory_only = _format_turn_results(turn_candidates, top_k)
    hybrid = _build_hybrid_results(
        question=query,
        category_results=category_results,
        turn_candidates=turn_candidates,
        resource_summary_results=resource_results,
        retriever=retriever,
        top_k=top_k,
    )
    selective, selective_decision = _build_selective_results(
        question=query,
        category_payload=category_only,
        turn_payload=turnmemory_only,
        turn_candidates=turn_candidates,
        resource_summary_results=resource_results,
        top_k=top_k,
    )
    return {
        "category_only": category_only,
        "turnmemory_only": turnmemory_only,
        "category_turn_resource_hybrid": hybrid,
        "category_turn_resource_selective": selective,
        "category_turn_resource_selective_decision": selective_decision,
    }


def _summary_counts(questions: list[dict[str, Any]], variant: str) -> dict[str, int]:
    current_correct = sum(1 for item in questions if item["current"]["is_correct"])
    variant_correct = sum(1 for item in questions if item[variant]["is_correct"])
    return {
        "correct": variant_correct,
        "gain": sum(1 for item in questions if item[variant]["is_correct"] and not item["current"]["is_correct"]),
        "regression": sum(1 for item in questions if item["current"]["is_correct"] and not item[variant]["is_correct"]),
        "nonempty_gold_gain": sum(
            1
            for item in questions
            if item["standard_answer"]
            and item[variant]["is_correct"]
            and not item["current"]["is_correct"]
        ),
        "empty_gold_regression": sum(
            1
            for item in questions
            if not item["standard_answer"]
            and item["current"]["is_correct"]
            and not item[variant]["is_correct"]
        ),
        "current_correct": current_correct,
    }


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Category + TurnMemory + Resource Evaluation",
        "",
        f"- generated_at_utc: `{report['generated_at_utc']}`",
        f"- character: `{report['character']}`",
        f"- user_id: `{report['user_id']}`",
        f"- qa_path: `{report['qa_path']}`",
        f"- top_k: `{report['top_k']}`",
        "",
        "## Summary",
        "",
    ]
    for name, payload in report["summary"]["variants"].items():
        lines.append(
            f"- {name}: correct=`{payload['correct']}/{report['summary']['total']}`, "
            f"gain=`{payload['gain']}`, regression=`{payload['regression']}`, "
            f"nonempty_gold_gain=`{payload['nonempty_gold_gain']}`, "
            f"empty_gold_regression=`{payload['empty_gold_regression']}`"
        )
    lines.extend(
        [
            f"- cache_hits: `{report['summary']['cache_hits']}`",
            f"- cache_misses: `{report['summary']['cache_misses']}`",
            f"- cache_hit_rate: `{report['summary']['cache_hit_rate']}`",
            "",
            "## Questions",
            "",
        ]
    )
    for item in report["questions"]:
        lines.extend(
            [
                f"### {item['question']}",
                "",
                f"- standard_answer: `{item['standard_answer']}`",
                f"- question_kind: `{item['question_kind']}`",
                f"- classified_categories: `{item['classified_categories']}`",
                f"- retrieval_seconds: `{item['retrieval_seconds']}`",
                f"- top_category: {item['top_category']}",
                f"- top_turnmemory: {item['top_turnmemory']}",
                f"- top_expanded_resource: {item['top_expanded_resource']}",
            ]
        )
        selective_decision = item.get("category_turn_resource_selective_decision", {})
        if selective_decision:
            lines.append(f"- selective_decision: `{selective_decision}`")
        for variant in (
            "current",
            "category_only",
            "turnmemory_only",
            "category_turn_resource_hybrid",
            "category_turn_resource_selective",
        ):
            payload = item[variant]
            lines.extend(
                [
                    f"- {variant}: correct=`{payload['is_correct']}`, anchor_rank=`{payload['answer_anchor_rank']}`, "
                    f"answer_seconds=`{payload['answer_seconds']}`",
                    f"  - strategies: `{payload['top_strategies']}`",
                    f"  - scores: `{payload['top_scores']}`",
                    f"  - answer: {payload['answer'][:300]}",
                ]
            )
        lines.append("")
    return "\n".join(lines)


async def run_eval(
    *,
    qa_path: Path,
    character: str,
    top_k: int,
    output_dir: Path,
    cache_path: Path,
) -> dict[str, Any]:
    qa_data = parse_qa_file(qa_path)
    questions = [
        question for question in qa_data.questions if question.target_character.lower() == character.lower()
    ]
    cache = _load_cache(cache_path)
    cache_stats = CacheStats()

    async with AsyncSessionLocal() as session:
        user = await _find_user(session, character)
        user_id = str(user.id)
        llm = LLMFactory.get_provider()
        retriever = MemoryRetriever(session, llm)
        resources, categories_by_resource = await _load_resources(session, user_id)
        question_reports: list[dict[str, Any]] = []

        for index, qa in enumerate(questions, 1):
            print(f"[{index}/{len(questions)}] {qa.question}")
            retrieval_started = time.perf_counter()
            query_vector = await _get_cached_embedding(
                llm,
                cache,
                cache_stats,
                namespace="queries",
                key=qa.question,
                text=qa.question,
            )
            classified_categories = await retriever._classify_query(user_id, qa.question)
            turn_candidates = await _rank_turnmemory(
                llm=llm,
                cache=cache,
                cache_stats=cache_stats,
                query_vector=query_vector,
                resources=resources,
                categories_by_resource=categories_by_resource,
                allowed_categories=classified_categories,
            )
            variant_inputs = await _build_variant_inputs(
                retriever=retriever,
                user_id=user_id,
                query=qa.question,
                top_k=top_k,
                classified_categories=classified_categories,
                turn_candidates=turn_candidates,
            )
            current_results = await retriever.retrieve(
                user_id=user_id,
                query=qa.question,
                top_k=top_k,
                use_llm_classification=True,
            )
            retrieval_seconds = round(time.perf_counter() - retrieval_started, 3)

            current_contexts, current_scores, _ = _extract_retrieval_observation(current_results)
            current_answer = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                top_k=top_k,
                results=current_results,
            )
            if current_contexts:
                current_answer["top_contexts"] = current_contexts[:5]
                current_answer["top_scores"] = [round(float(score), 4) for score in current_scores[:5]]
                current_answer["top_strategies"] = [result.get("strategy", "unknown") for result in current_results[:5]]

            category_only = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                top_k=top_k,
                results=variant_inputs["category_only"],
            )
            turnmemory_only = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                top_k=top_k,
                results=variant_inputs["turnmemory_only"],
            )
            hybrid = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                top_k=top_k,
                results=variant_inputs["category_turn_resource_hybrid"],
            )
            selective = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                top_k=top_k,
                results=variant_inputs["category_turn_resource_selective"],
            )

            top_category = ""
            if variant_inputs["category_only"]:
                cat = variant_inputs["category_only"][0].get("category")
                top_category = (cat.content if cat else "")[:300]
            top_turnmemory = turn_candidates[0].text[:300] if turn_candidates else ""
            top_expanded_resource = ""
            for result in variant_inputs["category_turn_resource_hybrid"]:
                if result.get("strategy") == "resource_expansion":
                    top_expanded_resource = result["resource"].description[:300]
                    break

            question_reports.append(
                {
                    "question": qa.question,
                    "standard_answer": qa.answer,
                    "evidence": qa.evidence,
                    "question_kind": _question_kind(qa.question),
                    "classified_categories": classified_categories,
                    "retrieval_seconds": retrieval_seconds,
                    "top_category": top_category,
                    "top_turnmemory": top_turnmemory,
                    "top_expanded_resource": top_expanded_resource,
                    "current": current_answer,
                    "category_only": category_only,
                    "turnmemory_only": turnmemory_only,
                    "category_turn_resource_hybrid": hybrid,
                    "category_turn_resource_selective": selective,
                    "category_turn_resource_selective_decision": variant_inputs[
                        "category_turn_resource_selective_decision"
                    ],
                }
            )
            _save_cache(cache_path, cache)

    total_cache = cache_stats.hits + cache_stats.misses
    summary = {
        "total": len(question_reports),
        "variants": {
            "current": {
                "correct": sum(1 for item in question_reports if item["current"]["is_correct"]),
                "gain": 0,
                "regression": 0,
                "nonempty_gold_gain": 0,
                "empty_gold_regression": 0,
                "current_correct": sum(1 for item in question_reports if item["current"]["is_correct"]),
            },
            "category_only": _summary_counts(question_reports, "category_only"),
            "turnmemory_only": _summary_counts(question_reports, "turnmemory_only"),
            "category_turn_resource_hybrid": _summary_counts(question_reports, "category_turn_resource_hybrid"),
            "category_turn_resource_selective": _summary_counts(
                question_reports,
                "category_turn_resource_selective",
            ),
        },
        "cache_hits": cache_stats.hits,
        "cache_misses": cache_stats.misses,
        "cache_hit_rate": round(cache_stats.hits / total_cache, 4) if total_cache else 0.0,
    }
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "qa_path": str(qa_path),
        "character": character,
        "user_id": user_id,
        "top_k": top_k,
        "summary": summary,
        "questions": question_reports,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    json_path = output_dir / f"category_turn_resource_eval_{stamp}.json"
    md_path = output_dir / f"category_turn_resource_eval_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["markdown_path"] = str(md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Category + TurnMemory + Resource evaluation for converted_data QA."
    )
    parser.add_argument("--qa-path", type=Path, default=DEFAULT_QA_PATH)
    parser.add_argument("--character", type=str, default="caroline")
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    args = parser.parse_args()

    report = asyncio.run(
        run_eval(
            qa_path=args.qa_path,
            character=args.character,
            top_k=args.top_k,
            output_dir=args.output_dir,
            cache_path=args.cache_path,
        )
    )
    print(f"json_report={report['json_path']}")
    print(f"markdown_report={report['markdown_path']}")
    print(f"summary={report['summary']}")


if __name__ == "__main__":
    main()
