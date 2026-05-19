from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import settings
from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever
from tests.evals.common import build_run_manifest, default_scoring_config_payload
from tests.evals.converted_data.rerank_eval import _result_document, _result_with_document
from tests.evals.converted_data.runner import _extract_retrieval_observation
from tests.evals.personamem_v2.analysis import (
    analyze_personamem_evidence,
    build_personamem_analysis_markdown,
    calculate_personamem_stage_metrics,
)
from tests.evals.personamem_v2.loader import DEFAULT_SPLIT, build_samples, load_personamem_rows
from tests.evals.personamem_v2.rerank_eval import (
    _evaluate_variant,
    _find_personamem_user,
    _load_questions_from_retrieval_json,
    _rank_from_analysis,
    _variant_metrics,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "test_results" / "personamem_v2"
DEFAULT_BM25_K1 = 1.2
DEFAULT_BM25_B = 0.75
BM25_LEGACY_DIAGNOSTIC_REASON = (
    "legacy_bm25_eval_may_run_online_retrieval_generation_and_evaluator; "
    "use personamem_v2_orthogonal rerank_ab with a retrieval_snapshot for formal A/B"
)

logger = logging.getLogger(__name__)


BM25_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "her",
    "hers",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "me",
    "might",
    "my",
    "of",
    "on",
    "or",
    "our",
    "ours",
    "please",
    "question",
    "answer",
    "she",
    "should",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "too",
    "us",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "yours",
}


@dataclass(frozen=True)
class BM25Document:
    original_index: int
    text: str
    tokens: list[str]
    term_counts: Counter[str]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def build_bm25_run_manifest(args: argparse.Namespace, *, question_count: int) -> dict[str, Any]:
    return build_run_manifest(
        harness="personamem_v2_legacy_bm25_rerank_diagnostic",
        eval_mode="assistant_eval",
        dataset="bowen-upenn/PersonaMem-v2",
        split=args.split,
        persona_id=args.persona_id,
        question_count=question_count,
        import_only=False,
        retrieval_only=True,
        reset_memory=False,
        chat_model=settings.chat_model,
        evaluator_model=settings.chat_model,
        evaluator_isolated=False,
        top_k=args.answer_top_k,
        scoring_config=default_scoring_config_payload(),
        rerank_config={
            "type": "bm25",
            "retrieve_top_k": args.retrieve_top_k,
            "answer_top_k": args.answer_top_k,
            "bm25_k1": args.bm25_k1,
            "bm25_b": args.bm25_b,
            "input_retrieval_json": str(args.input_retrieval_json) if args.input_retrieval_json else None,
        },
        extra={
            "formal_ab_eligible": False,
            "experiment_conclusion": "diagnostic_only",
            "diagnostic_reason": BM25_LEGACY_DIAGNOSTIC_REASON,
        },
    )


def tokenize_bm25_text(text: Any) -> list[str]:
    """Tokenize English PersonaMem text for deterministic BM25 evaluation."""
    tokens = re.findall(r"[A-Za-z0-9_'-]+", str(text or "").lower())
    return [
        token
        for token in tokens
        if len(token) > 1 and token not in BM25_STOPWORDS
    ]


def _build_bm25_documents(documents: list[str]) -> list[BM25Document]:
    built: list[BM25Document] = []
    for index, document in enumerate(documents):
        tokens = tokenize_bm25_text(document)
        if not str(document or "").strip():
            continue
        built.append(
            BM25Document(
                original_index=index,
                text=document,
                tokens=tokens,
                term_counts=Counter(tokens),
            )
        )
    return built


def _bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = DEFAULT_BM25_K1,
    b: float = DEFAULT_BM25_B,
) -> dict[int, float]:
    _validate_bm25_params(k1=k1, b=b)
    query_tokens = tokenize_bm25_text(query)
    built_docs = _build_bm25_documents(documents)
    if not query_tokens or not built_docs:
        return {}

    doc_lengths = [len(doc.tokens) for doc in built_docs]
    avg_doc_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0
    if avg_doc_len <= 0:
        return {}

    doc_freqs: Counter[str] = Counter()
    for doc in built_docs:
        doc_freqs.update(set(doc.tokens))

    scores: dict[int, float] = {}
    total_docs = len(built_docs)
    for doc in built_docs:
        score = 0.0
        doc_len = len(doc.tokens)
        if doc_len == 0:
            continue
        for term in query_tokens:
            term_frequency = doc.term_counts.get(term, 0)
            if term_frequency <= 0:
                continue
            doc_frequency = doc_freqs[term]
            idf = math.log(1 + (total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5))
            denominator = term_frequency + k1 * (1 - b + b * doc_len / avg_doc_len)
            score += idf * (term_frequency * (k1 + 1)) / denominator
        scores[doc.original_index] = score
    return scores


def bm25_rerank_results(
    *,
    query: str,
    retrieved_results: list[dict[str, Any]],
    top_n: int,
    k1: float = DEFAULT_BM25_K1,
    b: float = DEFAULT_BM25_B,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rerank existing retrieval candidates with Okapi BM25.

    This is intentionally evaluation-only: it does not query the database and
    does not mutate production retrieval behavior.
    """
    _validate_bm25_params(k1=k1, b=b)
    documents = [_result_document(result) for result in retrieved_results]
    if top_n <= 0:
        return [], {
            "candidate_count": len([doc for doc in documents if doc.strip()]),
            "top_n": top_n,
            "k1": k1,
            "b": b,
            "empty_query": not tokenize_bm25_text(query),
        }

    scores = _bm25_scores(query, documents, k1=k1, b=b)
    indexed_docs = [
        (index, document)
        for index, document in enumerate(documents)
        if document.strip()
    ]
    if not indexed_docs:
        return [], {
            "candidate_count": 0,
            "top_n": top_n,
            "k1": k1,
            "b": b,
            "empty_query": not tokenize_bm25_text(query),
        }

    if not scores:
        selected = indexed_docs[:top_n]
    else:
        selected = sorted(
            indexed_docs,
            key=lambda item: (scores.get(item[0], 0.0), -item[0]),
            reverse=True,
        )[:top_n]

    final_results: list[dict[str, Any]] = []
    for original_index, document in selected:
        score = float(scores.get(original_index, 0.0))
        cloned = _result_with_document(
            retrieved_results[original_index],
            document,
        )
        cloned["original_score"] = cloned.get("score", 0.0)
        cloned["score"] = score
        cloned["bm25_score"] = score
        final_results.append(cloned)

    return final_results, {
        "candidate_count": len(indexed_docs),
        "top_n": top_n,
        "k1": k1,
        "b": b,
        "empty_query": not tokenize_bm25_text(query),
    }


def _validate_bm25_params(*, k1: float, b: float) -> None:
    if k1 <= 0:
        raise ValueError("BM25 k1 must be > 0.")
    if b < 0 or b > 1:
        raise ValueError("BM25 b must be between 0 and 1.")


def _context_loose_rank(stage: dict[str, Any]) -> int | None:
    ranks = [
        stage.get("target_preference_rank"),
        stage.get("target_snippet_rank"),
        stage.get("target_answer_anchor_rank"),
        stage.get("answerable_context_rank"),
    ]
    valid_ranks = [rank for rank in ranks if isinstance(rank, int)]
    return min(valid_ranks) if valid_ranks else None


def _analyze_context_stage(
    *,
    question: Any,
    contexts: list[str],
    scores: list[float],
    stage: str,
) -> dict[str, Any]:
    first_pass = analyze_personamem_evidence(
        question=question.question,
        correct_answer=question.answer,
        supporting_preference=question.preference,
        related_conversation_snippet=question.related_conversation_snippet,
        incorrect_answers=question.incorrect_answers,
        contexts=contexts,
        scores=scores,
        stage=stage,
    )
    loose_rank = _context_loose_rank(first_pass)
    return analyze_personamem_evidence(
        question=question.question,
        correct_answer=question.answer,
        supporting_preference=question.preference,
        related_conversation_snippet=question.related_conversation_snippet,
        incorrect_answers=question.incorrect_answers,
        contexts=contexts,
        scores=scores,
        stage=stage,
        loose_rank_position=loose_rank,
        retrieval_hit_loose=loose_rank is not None,
    )


def _write_bm25_analysis(report: dict[str, Any], output_path: Path) -> Path:
    analysis_path = output_path.with_name(f"{output_path.stem}_analysis.md")
    sections = [
        "# PersonaMem-v2 BM25 Rerank Analysis",
        "",
        "## Summary",
        f"- Result file: `{output_path.name}`",
        f"- retrieve_top_k: {report.get('test_info', {}).get('retrieve_top_k')}",
        f"- answer_top_k: {report.get('test_info', {}).get('answer_top_k')}",
        f"- bm25_k1: {report.get('test_info', {}).get('bm25_k1')}",
        f"- bm25_b: {report.get('test_info', {}).get('bm25_b')}",
        "",
    ]
    for variant, results in (report.get("variants") or {}).items():
        pseudo = {
            "statistics": report.get("summary", {}).get(variant, {}),
            "samples": [{"qa_results": results}],
        }
        sections.extend(
            [
                f"## Variant: {variant}",
                build_personamem_analysis_markdown(pseudo, output_path.name),
                "",
            ]
        )
    analysis_path.write_text("\n".join(sections), encoding="utf-8")
    return analysis_path


def _validate_args(args: argparse.Namespace) -> None:
    _validate_bm25_params(k1=args.bm25_k1, b=args.bm25_b)


async def _find_eval_user(session: Any, *, persona_id: str, username: str | None) -> Any:
    if username:
        from sqlalchemy import select
        from tables import User

        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalars().first()
        if not user:
            raise ValueError(f"User '{username}' not found. Import this PersonaMem user before BM25 eval.")
        return user
    return await _find_personamem_user(session, persona_id)


async def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    _validate_args(args)
    offline_rows: list[tuple[Any, list[dict[str, Any]], dict[str, Any]]] | None = None
    if args.input_retrieval_json:
        offline_rows = _load_questions_from_retrieval_json(
            args.input_retrieval_json,
            persona_id=args.persona_id,
            max_questions=args.max_questions,
        )
        if not offline_rows:
            raise ValueError(
                f"No PersonaMem questions found in {args.input_retrieval_json} "
                f"for persona_id={args.persona_id}"
            )
        questions = [row[0] for row in offline_rows]
    else:
        rows = load_personamem_rows(split=args.split, max_rows=args.max_rows)
        samples = build_samples(
            rows,
            split=args.split,
            max_personas=1,
            max_questions=args.max_questions,
            persona_id=args.persona_id,
        )
        if not samples:
            raise ValueError(f"No PersonaMem questions found for persona_id={args.persona_id}")
        questions = samples[0].questions

    llm = LLMFactory.get_provider()
    current_results: list[dict[str, Any]] = []
    bm25_results_payload: list[dict[str, Any]] = []
    bm25_traces: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as session:
        user = await _find_eval_user(
            session,
            persona_id=args.persona_id,
            username=args.username,
        )
        retriever = None if offline_rows is not None else MemoryRetriever(session, llm)

        for index, question in enumerate(questions, start=1):
            logger.info("[%s/%s] %s", index, len(questions), question.question)
            if offline_rows is not None:
                retrieved = offline_rows[index - 1][1][: args.retrieve_top_k]
            else:
                assert retriever is not None
                retrieved = await retriever.retrieve(
                    user_id=user.id,
                    query=question.question,
                    top_k=args.retrieve_top_k,
                    use_llm_classification=True,
                    track_access=False,
                )

            raw_contexts, raw_scores, _ = _extract_retrieval_observation(retrieved)
            raw_retrieval_stage = _analyze_context_stage(
                question=question,
                contexts=raw_contexts,
                scores=raw_scores,
                stage="retrieval_raw_top_k",
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
                    variant="current_topk",
                    retrieval_stage=raw_retrieval_stage,
                    loose_rank_position=_rank_from_analysis(raw_retrieval_stage),
                )
            )

            bm25_ranked, trace = bm25_rerank_results(
                query=question.question,
                retrieved_results=retrieved,
                top_n=args.answer_top_k,
                k1=args.bm25_k1,
                b=args.bm25_b,
            )
            bm25_contexts, bm25_scores, _ = _extract_retrieval_observation(bm25_ranked)
            bm25_stage = _analyze_context_stage(
                question=question,
                contexts=bm25_contexts,
                scores=bm25_scores,
                stage="bm25_rerank_top_k",
            )
            bm25_traces.append(
                {
                    "question": question.question,
                    **trace,
                    "target_rank_before": raw_retrieval_stage.get("answerable_context_rank"),
                    "target_rank_after": bm25_stage.get("answerable_context_rank"),
                    "bm25_stage": bm25_stage,
                    "top_contexts": [_result_document(result)[:500] for result in bm25_ranked[:5]],
                    "top_scores": [round(float(result.get("bm25_score", 0.0)), 6) for result in bm25_ranked[:5]],
                }
            )
            bm25_results_payload.append(
                await _evaluate_variant(
                    session=session,
                    llm=llm,
                    user=user,
                    question=question,
                    results=bm25_ranked,
                    variant="bm25_rerank_topk",
                    retrieval_stage=raw_retrieval_stage,
                    loose_rank_position=bm25_stage.get("answerable_context_rank"),
                )
            )
            bm25_results_payload[-1]["rerank_stage"] = bm25_stage
            bm25_results_payload[-1]["bm25_stage"] = bm25_stage

    test_info = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "bowen-upenn/PersonaMem-v2",
        "harness": "personamem_v2_legacy_bm25_rerank_diagnostic",
        "split": args.split,
        "persona_id": args.persona_id,
        "username": user.username,
        "chat_model": settings.chat_model,
        "question_count": len(questions),
        "retrieve_top_k": args.retrieve_top_k,
        "answer_top_k": args.answer_top_k,
        "bm25_k1": args.bm25_k1,
        "bm25_b": args.bm25_b,
        "input_retrieval_json": str(args.input_retrieval_json) if args.input_retrieval_json else None,
        "mode": "offline_saved_retrieval" if args.input_retrieval_json else "online_retrieval",
        "formal_ab_eligible": False,
        "experiment_conclusion": "diagnostic_only",
        "diagnostic_reason": BM25_LEGACY_DIAGNOSTIC_REASON,
    }
    return {
        "test_info": {
            **test_info,
        },
        "run_manifest": build_bm25_run_manifest(args, question_count=len(questions)),
        "experiment_conclusion": "diagnostic_only",
        "formal_ab_eligible": False,
        "diagnostic_reason": BM25_LEGACY_DIAGNOSTIC_REASON,
        "summary": {
            "current_topk": _variant_metrics(current_results),
            "bm25_rerank_topk": _variant_metrics(bm25_results_payload),
        },
        "bm25_traces": bm25_traces,
        "variants": {
            "current_topk": current_results,
            "bm25_rerank_topk": bm25_results_payload,
        },
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Read-only BM25 rerank evaluation for PersonaMem-v2 QA.")
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--persona-id", default="66")
    parser.add_argument(
        "--username",
        help=(
            "PersonaMem DB username to evaluate. Defaults to "
            "personamem_v2_persona_{persona_id} when omitted."
        ),
    )
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--max-questions", type=int, default=42)
    parser.add_argument("--retrieve-top-k", type=int, default=30)
    parser.add_argument("--answer-top-k", type=int, default=15)
    parser.add_argument("--bm25-k1", type=float, default=DEFAULT_BM25_K1)
    parser.add_argument("--bm25-b", type=float, default=DEFAULT_BM25_B)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--input-retrieval-json",
        type=Path,
        help=(
            "Reuse a saved PersonaMem-v2 retrieval/assistant JSON instead of "
            "calling MemoryRetriever again."
        ),
    )
    args = parser.parse_args()

    report = asyncio.run(run_eval(args))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"personamem_v2_bm25_eval_{_now_stamp()}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_path = _write_bm25_analysis(report, output_path)
    logger.info("\nWrote %s", output_path)
    logger.info("Wrote %s", analysis_path)
    logger.info(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
