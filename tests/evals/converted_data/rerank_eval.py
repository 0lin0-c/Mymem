from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever
from tables import Category, Resource, User
from tests.evals.converted_data.loader import parse_qa_file
from tests.evals.converted_data.metrics import classify_answer_support_type
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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "test_results" / "retrieval"


@dataclass
class RerankItem:
    original_index: int
    result: dict[str, Any]
    document: str
    rerank_score: float


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _rerank_url() -> str:
    base_url = settings.embedding_base_url or settings.openai_base_url or ""
    if not base_url:
        raise ValueError("EMBEDDING_BASE_URL or OPENAI_BASE_URL is required for GLM rerank.")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        return f"{base_url}/p002/rerank"
    return f"{base_url}/v1/p002/rerank"


def _api_key() -> str:
    api_key = settings.embedding_api_key or settings.openai_api_key
    if not api_key:
        raise ValueError("EMBEDDING_API_KEY or OPENAI_API_KEY is required for GLM rerank.")
    return api_key


def _resource_clone(resource: Resource, description: str) -> Resource:
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


def _category_clone(category: Category, content: str) -> Category:
    return Category(
        id=category.id,
        user_id=category.user_id,
        category_name=category.category_name,
        content=content,
        content_vector=category.content_vector,
        importance_score=category.importance_score,
        access_count=category.access_count,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _result_document(result: dict[str, Any]) -> str:
    resource = result.get("resource")
    category = result.get("category")
    strategy = result.get("strategy", "")

    if strategy == "category_source_expansion" and resource is not None and category is not None:
        parts = [f"[{category.category_name}] fact: {category.content}"]
        if getattr(category, "created_at", None):
            parts.append(f"conversation_time: {category.created_at.isoformat()}")
        if getattr(resource, "description", None):
            parts.append(f"source_description: {resource.description}")
        if getattr(resource, "raw_content", None):
            parts.append(f"source_raw_content: {resource.raw_content}")
        return " | ".join(parts)

    if resource is not None:
        parts = []
        if category is not None:
            parts.append(f"[{category.category_name}]")
        if getattr(resource, "description", None):
            parts.append(str(resource.description))
        if getattr(resource, "raw_content", None):
            parts.append(f"source_raw_content: {resource.raw_content}")
        return " | ".join(parts)

    if category is not None:
        return f"[{category.category_name}] {category.content}"

    return ""


def _result_with_document(result: dict[str, Any], document: str, rerank_score: float | None = None) -> dict[str, Any]:
    cloned = dict(result)
    cloned["document_for_answer"] = document
    if rerank_score is not None:
        cloned["rerank_score"] = rerank_score

    resource = result.get("resource")
    category = result.get("category")
    if resource is not None:
        cloned["resource"] = _resource_clone(resource, document)
    elif category is not None:
        cloned["category"] = _category_clone(category, document)
    return cloned


def _extract_rerank_results(payload: dict[str, Any]) -> list[tuple[int, float]]:
    raw_results = payload.get("results")
    if raw_results is None:
        raw_results = payload.get("data")
    if raw_results is None and isinstance(payload.get("choices"), list):
        raw_results = payload["choices"]
    if not isinstance(raw_results, list):
        raise ValueError(f"Unexpected rerank response shape: {payload}")

    parsed: list[tuple[int, float]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        index = item.get("index", item.get("document_index"))
        score = item.get("relevance_score", item.get("score"))
        if index is None or score is None:
            continue
        parsed.append((int(index), float(score)))
    if not parsed:
        raise ValueError(f"Rerank response did not include index/score pairs: {payload}")
    return parsed


def rerank_results(
    *,
    query: str,
    retrieved_results: list[dict[str, Any]],
    model: str,
    top_n: int,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    docs = [_result_document(result) for result in retrieved_results]
    indexed_docs = [(index, doc) for index, doc in enumerate(docs) if doc.strip()]
    if not indexed_docs:
        return [], {"error": "no_documents"}

    request_payload = {
        "model": model,
        "query": query,
        "documents": [doc for _, doc in indexed_docs],
        "top_n": min(top_n, len(indexed_docs)),
    }
    started = time.perf_counter()
    response = requests.post(
        _rerank_url(),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        json=request_payload,
        timeout=timeout,
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    response.raise_for_status()
    payload = response.json()

    reranked: list[RerankItem] = []
    for local_index, score in _extract_rerank_results(payload):
        if local_index < 0 or local_index >= len(indexed_docs):
            continue
        original_index, document = indexed_docs[local_index]
        reranked.append(
            RerankItem(
                original_index=original_index,
                result=retrieved_results[original_index],
                document=document,
                rerank_score=score,
            )
        )

    reranked.sort(key=lambda item: item.rerank_score, reverse=True)
    final_results = [
        _result_with_document(item.result, item.document, item.rerank_score)
        for item in reranked[:top_n]
    ]
    return final_results, {
        "latency_ms": latency_ms,
        "candidate_count": len(indexed_docs),
        "top_n": top_n,
        "model": model,
    }


async def _find_user(session: Any, username: str) -> User:
    user = (
        await session.execute(select(User).where(User.username.ilike(username)))
    ).scalars().first()
    if not user:
        raise ValueError(f"User '{username}' not found in database.")
    return user


async def _evaluate_variant(
    *,
    session: Any,
    llm: Any,
    user: User,
    question: Any,
    results: list[dict[str, Any]],
    variant: str,
) -> dict[str, Any]:
    contexts, scores, layer_info = _extract_retrieval_observation(results)
    answer = await generate_answer_with_chat_orchestrator(
        session=session,
        llm=llm,
        user=user,
        user_id=user.id,
        question=question.question,
        top_k=len(results),
        retrieved_results=results,
    )
    is_correct, explanation = await evaluate_answer_correctness(
        llm,
        question.question,
        answer,
        question.answer,
    )
    return {
        "variant": variant,
        "question": question.question,
        "standard_answer": question.answer,
        "generated_answer": answer,
        "is_correct": is_correct,
        "correctness_explanation": explanation,
        "answer_support_type": classify_answer_support_type(
            {
                "question": question.question,
                "standard_answer": question.answer,
                "is_correct": is_correct,
                "retrieval_hit": None,
            }
        ),
        "retrieval_layer": {
            "resolved_layer": layer_info.resolved_layer,
            "llm_classified_categories": layer_info.llm_classified_categories,
            "category_results_count": layer_info.category_results_count,
            "resource_results_count": layer_info.resource_results_count,
            "low_confidence_fallback": layer_info.low_confidence_fallback,
        },
        "retrieved_contexts": contexts[:5],
        "retrieved_scores": [round(float(score), 4) for score in scores[:5]],
    }


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    correct = sum(1 for item in results if item.get("is_correct") is True)
    nonempty = [item for item in results if item.get("standard_answer")]
    nonempty_correct = sum(1 for item in nonempty if item.get("is_correct") is True)
    return {
        "total_questions": total,
        "correct_count": correct,
        "accuracy": (correct / total * 100) if total else 0,
        "nonempty_total": len(nonempty),
        "nonempty_correct_count": nonempty_correct,
        "nonempty_accuracy": (nonempty_correct / len(nonempty) * 100) if nonempty else 0,
    }


async def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    qa_data = parse_qa_file(args.qa_path)
    questions = [
        question
        for question in qa_data.questions
        if question.target_character.lower() == args.character.lower()
    ]
    if args.max_questions:
        questions = questions[: args.max_questions]

    llm = LLMFactory.get_provider()
    current_results: list[dict[str, Any]] = []
    rerank_results_payload: list[dict[str, Any]] = []
    rerank_traces: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as session:
        user = await _find_user(session, args.character)
        retriever = MemoryRetriever(session, llm)

        for index, question in enumerate(questions, start=1):
            print(f"[{index}/{len(questions)}] {question.question}")
            retrieved = await retriever.retrieve(
                user_id=user.id,
                query=question.question,
                top_k=args.retrieve_top_k,
                use_llm_classification=True,
            )
            current_slice = [
                _result_with_document(result, _result_document(result))
                for result in retrieved[: args.answer_top_k]
            ]
            current_results.append(
                await _evaluate_variant(
                    session=session,
                    llm=llm,
                    user=user,
                    question=question,
                    results=current_slice,
                    variant="current_top30",
                )
            )

            reranked, trace = rerank_results(
                query=question.question,
                retrieved_results=retrieved,
                model=args.rerank_model,
                top_n=args.answer_top_k,
                timeout=args.timeout,
            )
            rerank_traces.append({
                "question": question.question,
                **trace,
                "top_contexts": [_result_document(result)[:500] for result in reranked[:5]],
                "top_scores": [result.get("rerank_score") for result in reranked[:5]],
            })
            rerank_results_payload.append(
                await _evaluate_variant(
                    session=session,
                    llm=llm,
                    user=user,
                    question=question,
                    results=reranked,
                    variant="glm_rerank_top30",
                )
            )

    return {
        "test_info": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "qa_path": str(args.qa_path),
            "character": args.character,
            "retrieve_top_k": args.retrieve_top_k,
            "answer_top_k": args.answer_top_k,
            "rerank_model": args.rerank_model,
        },
        "summary": {
            "current_top30": _summarize(current_results),
            "glm_rerank_top30": _summarize(rerank_results_payload),
        },
        "rerank_traces": rerank_traces,
        "variants": {
            "current_top30": current_results,
            "glm_rerank_top30": rerank_results_payload,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only GLM rerank evaluation for converted_data QA.")
    parser.add_argument("--qa-path", type=Path, default=DEFAULT_QA_PATH)
    parser.add_argument("--character", default="caroline")
    parser.add_argument("--retrieve-top-k", type=int, default=30)
    parser.add_argument("--answer-top-k", type=int, default=15)
    parser.add_argument("--rerank-model", default="GLM-Rerank")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-questions", type=int)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = asyncio.run(run_eval(args))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"glm_rerank_eval_{_now_stamp()}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {output_path}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
