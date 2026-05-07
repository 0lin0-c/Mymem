from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever
from tables import User
from tests.evals.converted_data.metrics import classify_answer_support_type
from tests.evals.converted_data.rerank_eval import (
    _result_document,
    _result_with_document,
    _summarize,
    rerank_results,
)
from tests.evals.converted_data.runner import (
    _extract_retrieval_observation,
    evaluate_answer_correctness,
    generate_answer_with_chat_orchestrator,
)
from tests.evals.personamem_v2.analysis import (
    analyze_personamem_evidence,
    build_personamem_analysis_markdown,
    calculate_personamem_stage_metrics,
)
from tests.evals.personamem_v2.loader import DEFAULT_SPLIT, build_samples, load_personamem_rows


REPO_ROOT = Path(__file__).parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "test_results" / "personamem_v2"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


async def _find_personamem_user(session: Any, persona_id: str) -> User:
    username = f"personamem_v2_persona_{persona_id}"
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalars().first()
    if not user:
        raise ValueError(
            f"User '{username}' not found. Import this PersonaMem persona before rerank eval."
        )
    return user


def _fake_retrieved_result_from_context(
    context: str,
    *,
    score: float = 0.0,
    strategy: str = "offline_context",
) -> dict[str, Any]:
    return {
        "resource": SimpleNamespace(
            id=None,
            user_id=None,
            modality="text",
            description=str(context or ""),
            description_vector=None,
            raw_content="",
            importance_score=0,
            assistant_response="",
            access_count=0,
            created_at=None,
            updated_at=None,
        ),
        "category": None,
        "score": float(score or 0.0),
        "strategy": strategy,
    }


def _fake_retrieved_results_from_saved_qa(qa: dict[str, Any]) -> list[dict[str, Any]]:
    contexts = list(qa.get("retrieved_contexts") or qa.get("retrieved_contexts_preview") or [])
    scores = list(qa.get("retrieved_scores") or qa.get("retrieved_scores_preview") or [])
    results: list[dict[str, Any]] = []
    for index, context in enumerate(contexts):
        score = scores[index] if index < len(scores) and isinstance(scores[index], (int, float)) else 0.0
        results.append(_fake_retrieved_result_from_context(context, score=score))
    return results


def _question_from_saved_qa(qa: dict[str, Any], fallback_persona_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        persona_id=str(qa.get("persona_id") or fallback_persona_id),
        row_index=qa.get("row_index"),
        pref_type=str(qa.get("pref_type") or ""),
        updated=str(qa.get("updated") or ""),
        who=str(qa.get("who") or ""),
        question=str(qa.get("question") or ""),
        answer=str(qa.get("correct_answer") or qa.get("standard_answer") or ""),
        incorrect_answers=list(qa.get("incorrect_answers") or []),
        preference=str(qa.get("supporting_preference") or qa.get("preference") or ""),
        related_conversation_snippet=str(qa.get("related_conversation_snippet") or ""),
    )


def _load_questions_from_retrieval_json(
    input_path: Path,
    *,
    persona_id: str | None,
    max_questions: int,
) -> list[tuple[SimpleNamespace, list[dict[str, Any]], dict[str, Any]]]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    fallback_persona_id = str(
        persona_id
        or (payload.get("test_info") or {}).get("persona_id")
        or ""
    )
    rows: list[tuple[SimpleNamespace, list[dict[str, Any]], dict[str, Any]]] = []
    for sample in payload.get("samples", []):
        sample_persona = str(sample.get("persona_id") or sample.get("character") or fallback_persona_id)
        if persona_id and sample_persona != str(persona_id):
            continue
        for qa in sample.get("qa_results", []):
            question = _question_from_saved_qa(qa, sample_persona or fallback_persona_id)
            retrieved = _fake_retrieved_results_from_saved_qa(qa)
            rows.append((question, retrieved, qa))
            if max_questions and len(rows) >= max_questions:
                return rows
    return rows


async def _evaluate_variant(
    *,
    session: Any,
    llm: Any,
    user: User,
    question: Any,
    results: list[dict[str, Any]],
    variant: str,
    retrieval_stage: dict[str, Any] | None = None,
    loose_rank_position: int | None = None,
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
    answer_stage = analyze_personamem_evidence(
        question=question.question,
        correct_answer=question.answer,
        supporting_preference=question.preference,
        related_conversation_snippet=question.related_conversation_snippet,
        incorrect_answers=question.incorrect_answers,
        contexts=contexts,
        scores=scores,
        stage=f"{variant}_answer_context",
        loose_rank_position=loose_rank_position,
        retrieval_hit_loose=loose_rank_position is not None,
        generated_answer=answer,
        is_correct=is_correct,
    )
    return {
        "variant": variant,
        "persona_id": question.persona_id,
        "row_index": question.row_index,
        "pref_type": question.pref_type,
        "updated": question.updated,
        "who": question.who,
        "question": question.question,
        "standard_answer": question.answer,
        "incorrect_answers": question.incorrect_answers,
        "supporting_preference": question.preference,
        "related_conversation_snippet": question.related_conversation_snippet,
        "generated_answer": answer,
        "is_correct": is_correct,
        "correctness_explanation": explanation,
        "answer_support_type": answer_stage["answer_support_type"]
        or classify_answer_support_type(
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
        "retrieval_stage": retrieval_stage or {},
        "answer_stage": answer_stage,
        "retrieved_contexts": contexts,
        "retrieved_contexts_preview": contexts[:5],
        "retrieved_scores": [round(float(score), 4) for score in scores],
        "retrieved_scores_preview": [round(float(score), 4) for score in scores[:5]],
    }


def _rank_from_analysis(analysis: dict[str, Any]) -> int | None:
    rank = analysis.get("answerable_context_rank") or analysis.get("target_answer_anchor_rank")
    return rank if isinstance(rank, int) else None


def _variant_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _summarize(results)
    summary["personamem_evidence"] = {
        "retrieval_stage": calculate_personamem_stage_metrics(
            results,
            stage_key="retrieval_stage",
        ),
        "rerank_stage": calculate_personamem_stage_metrics(
            results,
            stage_key="rerank_stage",
        ),
        "answer_stage": calculate_personamem_stage_metrics(
            results,
            stage_key="answer_stage",
        ),
    }
    return summary


def _write_rerank_analysis(report: dict[str, Any], output_path: Path) -> Path:
    analysis_path = output_path.with_name(f"{output_path.stem}_analysis.md")
    sections = [
        "# PersonaMem-v2 Rerank Analysis",
        "",
        "## Summary",
        f"- Result file: `{output_path.name}`",
        f"- retrieve_top_k: {report.get('test_info', {}).get('retrieve_top_k')}",
        f"- answer_top_k: {report.get('test_info', {}).get('answer_top_k')}",
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


async def run_eval(args: argparse.Namespace) -> dict[str, Any]:
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
        sample = samples[0]
        questions = sample.questions

    llm = LLMFactory.get_provider()
    current_results: list[dict[str, Any]] = []
    rerank_results_payload: list[dict[str, Any]] = []
    rerank_traces: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as session:
        user = await _find_personamem_user(session, args.persona_id)
        retriever = None if offline_rows is not None else MemoryRetriever(session, llm)

        for index, question in enumerate(questions, start=1):
            print(f"[{index}/{len(questions)}] {question.question}")
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
            raw_retrieval_stage = analyze_personamem_evidence(
                question=question.question,
                correct_answer=question.answer,
                supporting_preference=question.preference,
                related_conversation_snippet=question.related_conversation_snippet,
                incorrect_answers=question.incorrect_answers,
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

            reranked, trace = rerank_results(
                query=question.question,
                retrieved_results=retrieved,
                model=args.rerank_model,
                top_n=args.answer_top_k,
                timeout=args.timeout,
            )
            rerank_contexts, rerank_scores, _ = _extract_retrieval_observation(reranked)
            rerank_stage = analyze_personamem_evidence(
                question=question.question,
                correct_answer=question.answer,
                supporting_preference=question.preference,
                related_conversation_snippet=question.related_conversation_snippet,
                incorrect_answers=question.incorrect_answers,
                contexts=rerank_contexts,
                scores=rerank_scores,
                stage="rerank_top_k",
                loose_rank_position=_rank_from_analysis(raw_retrieval_stage),
                retrieval_hit_loose=raw_retrieval_stage.get("retrieval_hit_loose"),
            )
            rerank_traces.append(
                {
                    "question": question.question,
                    **trace,
                    "target_rank_before": raw_retrieval_stage.get("answerable_context_rank"),
                    "target_rank_after": rerank_stage.get("answerable_context_rank"),
                    "rerank_stage": rerank_stage,
                    "top_contexts": [_result_document(result)[:500] for result in reranked[:5]],
                    "top_scores": [result.get("rerank_score") for result in reranked[:5]],
                }
            )
            rerank_results_payload.append(
                await _evaluate_variant(
                    session=session,
                    llm=llm,
                    user=user,
                    question=question,
                    results=reranked,
                    variant="glm_rerank_topk",
                    retrieval_stage=raw_retrieval_stage,
                    loose_rank_position=rerank_stage.get("answerable_context_rank"),
                )
            )
            rerank_results_payload[-1]["rerank_stage"] = rerank_stage

    return {
        "test_info": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset": "bowen-upenn/PersonaMem-v2",
            "split": args.split,
            "persona_id": args.persona_id,
            "username": f"personamem_v2_persona_{args.persona_id}",
            "question_count": len(questions),
            "retrieve_top_k": args.retrieve_top_k,
            "answer_top_k": args.answer_top_k,
            "rerank_model": args.rerank_model,
            "input_retrieval_json": str(args.input_retrieval_json) if args.input_retrieval_json else None,
            "mode": "offline_saved_retrieval" if args.input_retrieval_json else "online_retrieval",
        },
        "summary": {
            "current_topk": _variant_metrics(current_results),
            "glm_rerank_topk": _variant_metrics(rerank_results_payload),
        },
        "rerank_traces": rerank_traces,
        "variants": {
            "current_topk": current_results,
            "glm_rerank_topk": rerank_results_payload,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only GLM rerank evaluation for PersonaMem-v2 QA.")
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--persona-id", default="66")
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--max-questions", type=int, default=42)
    parser.add_argument("--retrieve-top-k", type=int, default=30)
    parser.add_argument("--answer-top-k", type=int, default=15)
    parser.add_argument("--rerank-model", default="GLM-Rerank")
    parser.add_argument("--timeout", type=int, default=60)
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
    output_path = args.output_dir / f"personamem_v2_rerank_eval_{_now_stamp()}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_path = _write_rerank_analysis(report, output_path)
    print(f"\nWrote {output_path}")
    print(f"Wrote {analysis_path}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
