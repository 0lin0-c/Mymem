from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
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
DEFAULT_CACHE_PATH = REPO_ROOT / "test_results" / "cache" / "raw_content_embedding_cache.json"


@dataclass
class RawResourceCandidate:
    resource: Resource
    raw_context: str
    score: float
    similarity: float
    category_names: list[str]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _score_raw_resource(
    *,
    query_vector: list[float],
    raw_vector: list[float],
    resource: Resource,
) -> tuple[float, float]:
    config = DEFAULT_RETRIEVAL_SCORING_CONFIG
    similarity = _cosine_similarity(query_vector, raw_vector)
    similarity_factor = pow(similarity, config.similarity_power)
    access_factor = pow(math.log((resource.access_count or 0) + 2), config.access_power)
    recency_factor = pow(
        math.exp(-0.693 * _days_ago(resource.updated_at) / config.recency_decay_days),
        config.recency_power,
    )
    importance_factor = pow(0.7 + ((resource.importance_score or 0) / 10.0), config.importance_power)
    return similarity_factor * access_factor * recency_factor * importance_factor, similarity


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"resources": {}, "queries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("resources", {})
    data.setdefault("queries", {})
    return data


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


async def _get_cached_embedding(
    llm: Any,
    cache: dict[str, Any],
    *,
    namespace: str,
    key: str,
    text: str,
) -> list[float]:
    text_hash = _hash_text(text)
    cached = cache[namespace].get(key)
    if cached and cached.get("hash") == text_hash:
        return [float(value) for value in cached["embedding"]]
    embedding = await llm.get_embedding(text)
    cache[namespace][key] = {"hash": text_hash, "embedding": embedding}
    return embedding


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


def _clone_resource_with_raw_description(resource: Resource) -> Resource:
    return Resource(
        id=resource.id,
        user_id=resource.user_id,
        modality=resource.modality,
        raw_content=resource.raw_content,
        description=resource.raw_content,
        description_vector=resource.description_vector,
        importance_score=resource.importance_score,
        created_at=resource.created_at,
        assistant_response=resource.assistant_response,
        access_count=resource.access_count,
        updated_at=resource.updated_at,
    )


def _to_retrieval_results(candidates: list[RawResourceCandidate], top_k: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for candidate in candidates[:top_k]:
        results.append(
            {
                "resource": _clone_resource_with_raw_description(candidate.resource),
                "score": candidate.score,
                "strategy": "raw_resource_vector",
                "raw_similarity": candidate.similarity,
                "raw_category_names": candidate.category_names,
            }
        )
    return results


async def _rank_raw_resources(
    *,
    llm: Any,
    cache: dict[str, Any],
    query: str,
    query_vector: list[float],
    resources: list[Resource],
    categories_by_resource: dict[str, list[str]],
    allowed_categories: list[str] | None,
) -> list[RawResourceCandidate]:
    allowed = set(allowed_categories or [])
    candidates: list[RawResourceCandidate] = []
    for index, resource in enumerate(resources, 1):
        category_names = categories_by_resource.get(str(resource.id), [])
        if allowed and not (allowed & set(category_names)):
            continue
        raw_content = resource.raw_content or ""
        if not raw_content.strip():
            continue
        raw_vector = await _get_cached_embedding(
            llm,
            cache,
            namespace="resources",
            key=str(resource.id),
            text=raw_content,
        )
        score, similarity = _score_raw_resource(
            query_vector=query_vector,
            raw_vector=raw_vector,
            resource=resource,
        )
        candidates.append(
            RawResourceCandidate(
                resource=resource,
                raw_context=raw_content,
                score=score,
                similarity=similarity,
                category_names=category_names,
            )
        )
        if index % 50 == 0:
            print(f"  embedded/scored {index} resources for: {query[:60]}")
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates


def _contexts_and_scores(results: list[dict[str, Any]]) -> tuple[list[str], list[float], list[float]]:
    contexts: list[str] = []
    scores: list[float] = []
    similarities: list[float] = []
    for result in results:
        resource = result.get("resource")
        if resource and resource.description:
            contexts.append(resource.description)
            scores.append(float(result.get("score", 0.0)))
            similarities.append(float(result.get("raw_similarity", 0.0)))
    return contexts, scores, similarities


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
    results: list[dict[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    contexts, scores, similarities = _contexts_and_scores(results)
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
        "top_contexts": [context[:500] for context in contexts[:5]],
        "top_scores": [round(score, 4) for score in scores[:5]],
        "top_similarities": [round(similarity, 4) for similarity in similarities[:5]],
    }


def _build_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Raw Resource Content Evaluation",
        "",
        f"- generated_at_utc: `{report['generated_at_utc']}`",
        f"- character: `{report['character']}`",
        f"- user_id: `{report['user_id']}`",
        f"- qa_path: `{report['qa_path']}`",
        f"- top_k: `{report['top_k']}`",
        "",
        "## Summary",
        "",
        f"- current_correct: `{summary['current_correct']}/{summary['total']}`",
        f"- raw_routed_correct: `{summary['raw_routed_correct']}/{summary['total']}`",
        f"- raw_global_correct: `{summary['raw_global_correct']}/{summary['total']}`",
        f"- raw_routed_gain: `{summary['raw_routed_gain']}`",
        f"- raw_global_gain: `{summary['raw_global_gain']}`",
        f"- raw_routed_regression: `{summary['raw_routed_regression']}`",
        f"- raw_global_regression: `{summary['raw_global_regression']}`",
        "",
        "## Questions",
        "",
    ]
    for item in report["questions"]:
        lines.extend(
            [
                f"### {item['question']}",
                "",
                f"- standard_answer: `{item['standard_answer']}`",
                f"- classified_categories: `{item['classified_categories']}`",
                f"- current: correct=`{item['current']['is_correct']}`, anchor_rank=`{item['current']['answer_anchor_rank']}`",
                f"- raw_routed: correct=`{item['raw_routed']['is_correct']}`, anchor_rank=`{item['raw_routed']['answer_anchor_rank']}`, scores=`{item['raw_routed']['top_scores']}`, sims=`{item['raw_routed']['top_similarities']}`",
                f"- raw_global: correct=`{item['raw_global']['is_correct']}`, anchor_rank=`{item['raw_global']['answer_anchor_rank']}`, scores=`{item['raw_global']['top_scores']}`, sims=`{item['raw_global']['top_similarities']}`",
                f"- current_answer: {item['current']['answer'][:300]}",
                f"- raw_routed_answer: {item['raw_routed']['answer'][:300]}",
                f"- raw_global_answer: {item['raw_global']['answer'][:300]}",
                "",
            ]
        )
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
    questions = [question for question in qa_data.questions if question.target_character.lower() == character.lower()]
    cache = _load_cache(cache_path)

    async with AsyncSessionLocal() as session:
        user = await _find_user(session, character)
        user_id = str(user.id)
        llm = LLMFactory.get_provider()
        retriever = MemoryRetriever(session, llm)
        resources, categories_by_resource = await _load_resources(session, user_id)

        question_reports: list[dict[str, Any]] = []
        for index, qa in enumerate(questions, 1):
            print(f"[{index}/{len(questions)}] {qa.question}")
            query_vector = await _get_cached_embedding(
                llm,
                cache,
                namespace="queries",
                key=qa.question,
                text=qa.question,
            )
            classified_categories = await retriever._classify_query(user_id, qa.question)

            current_results = await retriever.retrieve(
                user_id=user_id,
                query=qa.question,
                top_k=top_k,
                use_llm_classification=True,
            )
            current_contexts, current_scores, _ = _extract_retrieval_observation(current_results)
            current_answer = await generate_answer_with_chat_orchestrator(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                top_k=top_k,
                retrieved_results=current_results,
            ) if current_contexts else ""
            current_correct, current_explanation = await evaluate_answer_correctness(
                llm,
                qa.question,
                current_answer,
                qa.answer,
            )

            raw_routed_candidates = await _rank_raw_resources(
                llm=llm,
                cache=cache,
                query=qa.question,
                query_vector=query_vector,
                resources=resources,
                categories_by_resource=categories_by_resource,
                allowed_categories=classified_categories,
            )
            raw_global_candidates = await _rank_raw_resources(
                llm=llm,
                cache=cache,
                query=qa.question,
                query_vector=query_vector,
                resources=resources,
                categories_by_resource=categories_by_resource,
                allowed_categories=None,
            )
            raw_routed_results = _to_retrieval_results(raw_routed_candidates, top_k)
            raw_global_results = _to_retrieval_results(raw_global_candidates, top_k)

            raw_routed = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                results=raw_routed_results,
                top_k=top_k,
            )
            raw_global = await _answer_variant(
                session=session,
                llm=llm,
                user=user,
                user_id=user_id,
                question=qa.question,
                standard_answer=qa.answer,
                results=raw_global_results,
                top_k=top_k,
            )

            question_reports.append(
                {
                    "question": qa.question,
                    "standard_answer": qa.answer,
                    "evidence": qa.evidence,
                    "classified_categories": classified_categories,
                    "current": {
                        "is_correct": current_correct,
                        "answer": current_answer,
                        "explanation": current_explanation,
                        "answer_anchor_rank": _answer_anchor_hit(qa.answer, current_contexts),
                        "top_contexts": current_contexts[:5],
                        "top_scores": [round(float(score), 4) for score in current_scores[:5]],
                    },
                    "raw_routed": raw_routed,
                    "raw_global": raw_global,
                }
            )
            _save_cache(cache_path, cache)

    total = len(question_reports)
    current_correct = sum(1 for item in question_reports if item["current"]["is_correct"])
    raw_routed_correct = sum(1 for item in question_reports if item["raw_routed"]["is_correct"])
    raw_global_correct = sum(1 for item in question_reports if item["raw_global"]["is_correct"])
    summary = {
        "total": total,
        "current_correct": current_correct,
        "raw_routed_correct": raw_routed_correct,
        "raw_global_correct": raw_global_correct,
        "raw_routed_gain": sum(
            1 for item in question_reports if item["raw_routed"]["is_correct"] and not item["current"]["is_correct"]
        ),
        "raw_global_gain": sum(
            1 for item in question_reports if item["raw_global"]["is_correct"] and not item["current"]["is_correct"]
        ),
        "raw_routed_regression": sum(
            1 for item in question_reports if item["current"]["is_correct"] and not item["raw_routed"]["is_correct"]
        ),
        "raw_global_regression": sum(
            1 for item in question_reports if item["current"]["is_correct"] and not item["raw_global"]["is_correct"]
        ),
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
    json_path = output_dir / f"raw_resource_eval_{stamp}.json"
    md_path = output_dir / f"raw_resource_eval_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["markdown_path"] = str(md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only evaluation of raw_content embeddings for Resource-layer retrieval."
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
