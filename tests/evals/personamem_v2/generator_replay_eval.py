from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from core.config import settings
from services.chat_orchestrator import ChatOrchestrator
from services.llm.factory import LLMFactory
from tests.evals.common import build_run_manifest, finalize_run_manifest, stable_payload_hash
from tests.evals.converted_data.runner import evaluate_answer_correctness
from tests.evals.personamem_v2.analysis import analyze_personamem_evidence
from tests.evals.personamem_v2.orthogonal_eval import load_json_file
from tests.evals.personamem_v2.runner import _get_provider_for_model, _temporary_chat_model


DEFAULT_OUTPUT_DIR = Path("test_results") / "personamem_v2" / "diagnostic" / "generator_replay"


async def replay_generator_from_context_snapshot(
    context_snapshot: dict[str, Any],
    *,
    chat_model: str,
    evaluator_model: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    user_prompt_template: str | None = None,
    agent_persona_template: str | None = None,
) -> dict[str, Any]:
    """Generate answers from a fixed context snapshot as a generator_ab input artifact.

    This standalone replay is diagnostic by itself. A formal generator A/B must
    consume two such fixed-context variants through the orthogonal report
    contract and produce paired evidence-first statistics.
    """
    items = list(context_snapshot.get("items") or [])
    evaluator_llm = _get_provider_for_model(evaluator_model)
    qa_results: list[dict[str, Any]] = []

    with _temporary_chat_model(chat_model):
        generator_llm = LLMFactory.get_provider()
        orchestrator = ChatOrchestrator(session=None, llm=generator_llm)  # type: ignore[arg-type]
        for index, item in enumerate(items):
            contexts = list(item.get("answer_contexts") or item.get("retrieved_contexts") or [])
            context_text = _format_fixed_answer_context(contexts)
            question = str(item.get("question") or "")
            generated_answer = await _generate_with_fixed_context(
                orchestrator=orchestrator,
                question=question,
                context_text=context_text,
                user_prompt_template=user_prompt_template,
                agent_persona_template=agent_persona_template,
            )
            is_correct, explanation = await evaluate_answer_correctness(
                evaluator_llm,
                question,
                generated_answer,
                str(item.get("standard_answer") or item.get("correct_answer") or ""),
            )
            qa_results.append(
                _qa_from_context_item(
                    item,
                    index=index,
                    chat_model=chat_model,
                    evaluator_model=evaluator_model,
                    generated_answer=generated_answer,
                    is_correct=is_correct,
                    correctness_explanation=explanation,
                )
            )

    manifest = build_run_manifest(
        harness="personamem_v2_generator_replay",
        eval_mode="generator_ab_variant",
        dataset="bowen-upenn/PersonaMem-v2",
        split="benchmark_text",
        persona_id=context_snapshot.get("persona_id"),
        question_count=len(qa_results),
        import_only=False,
        retrieval_only=True,
        reset_memory=False,
        chat_model=chat_model,
        evaluator_model=evaluator_model,
        evaluator_isolated=True,
        top_k=None,
        scoring_config=None,
        rerank_config=None,
        db_snapshot_id=context_snapshot.get("db_snapshot_id"),
        dataset_hash=stable_payload_hash(context_snapshot),
        cache_hash=stable_payload_hash(
            {
                "source_context_snapshot": (context_snapshot.get("run_manifest") or {}).get("run_id"),
                "chat_model": chat_model,
                "evaluator_model": evaluator_model,
            }
        ),
        temperature=0.7,
        extra={
            "formal_ab_variant_for": "generator_ab",
            "formal_ab_eligible": False,
            "experiment_conclusion": "diagnostic_only",
            "diagnostic_reason": "generator_replay_variant_requires_orthogonal_pairing",
            "source_context_snapshot_run_id": (context_snapshot.get("run_manifest") or {}).get("run_id"),
        },
    )
    report = {
        "test_info": {
            "dataset": "bowen-upenn/PersonaMem-v2",
            "harness": "personamem_v2_generator_replay",
            "chat_model": chat_model,
            "evaluator_model": evaluator_model,
            "source_context_snapshot_run_id": (context_snapshot.get("run_manifest") or {}).get("run_id"),
            "formal_ab_variant_for": "generator_ab",
            "formal_ab_eligible": False,
            "experiment_conclusion": "diagnostic_only",
            "diagnostic_reason": "generator_replay_variant_requires_orthogonal_pairing",
        },
        "run_manifest": manifest,
        "formal_ab_eligible": False,
        "experiment_conclusion": "diagnostic_only",
        "diagnostic_reason": "generator_replay_variant_requires_orthogonal_pairing",
        "variant": {
            "name": chat_model,
            "chat_model": chat_model,
            "evaluator_model": evaluator_model,
            "qa_results": qa_results,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"personamem_v2_generator_replay_{_safe_name(chat_model)}.json"
    finalize_run_manifest(report["run_manifest"], result_file_path=output_path)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["path"] = str(output_path)
    return report


async def _generate_with_fixed_context(
    *,
    orchestrator: ChatOrchestrator,
    question: str,
    context_text: str,
    user_prompt_template: str | None,
    agent_persona_template: str | None,
) -> str:
    chunks: list[str] = []
    async for chunk in orchestrator.stream(
        user_id="personamem_v2_generator_replay",
        user_query=question,
        user_prompt_template=user_prompt_template,
        agent_persona_template=agent_persona_template,
        pending_chats=[],
        retrieved_results=[],
        retrieved_context=context_text,
    ):
        chunks.append(chunk)
    return "".join(chunks).strip() or "I don't have enough information to answer this question."


def _qa_from_context_item(
    item: dict[str, Any],
    *,
    index: int,
    chat_model: str,
    evaluator_model: str,
    generated_answer: str,
    is_correct: bool,
    correctness_explanation: str,
) -> dict[str, Any]:
    contexts = list(item.get("answer_contexts") or item.get("retrieved_contexts") or [])
    scores = list(item.get("context_scores") or item.get("retrieved_scores") or [])
    qa = {
        "question_id": str(item.get("question_id") or item.get("row_index") or f"q{index}"),
        "persona_id": item.get("persona_id"),
        "source_split": item.get("source_split"),
        "row_index": item.get("row_index", index),
        "question": item.get("question"),
        "standard_answer": item.get("standard_answer") or item.get("correct_answer"),
        "correct_answer": item.get("standard_answer") or item.get("correct_answer"),
        "supporting_preference": item.get("supporting_preference") or item.get("preference") or "",
        "related_conversation_snippet": item.get("related_conversation_snippet") or "",
        "incorrect_answers": list(item.get("incorrect_answers") or []),
        "retrieved_contexts": contexts,
        "retrieved_scores": scores,
        "retrieval_candidate_contexts": list(item.get("retrieval_candidate_contexts") or contexts),
        "retrieval_candidate_scores": list(item.get("retrieval_candidate_scores") or scores),
        "generated_answer": generated_answer,
        "is_correct": is_correct,
        "correctness_explanation": correctness_explanation,
        "chat_model": chat_model,
        "evaluator_model": evaluator_model,
    }
    qa["retrieval_stage"] = analyze_personamem_evidence(
        question=str(qa["question"] or ""),
        correct_answer=str(qa["standard_answer"] or ""),
        supporting_preference=str(qa["supporting_preference"] or ""),
        related_conversation_snippet=str(qa["related_conversation_snippet"] or ""),
        incorrect_answers=qa["incorrect_answers"],
        contexts=contexts,
        scores=scores,
        stage="fixed_answer_context",
        retrieval_hit_loose=bool(contexts),
    )
    qa["answer_stage"] = analyze_personamem_evidence(
        question=str(qa["question"] or ""),
        correct_answer=str(qa["standard_answer"] or ""),
        supporting_preference=str(qa["supporting_preference"] or ""),
        related_conversation_snippet=str(qa["related_conversation_snippet"] or ""),
        incorrect_answers=qa["incorrect_answers"],
        contexts=contexts,
        scores=scores,
        stage="generator_answer",
        retrieval_hit_loose=bool(contexts),
        generated_answer=generated_answer,
        is_correct=is_correct,
    )
    return qa


def _format_fixed_answer_context(contexts: list[str]) -> str:
    if not contexts:
        return ""
    lines = ["# Retrieved Memories", "## Fixed Answer Context"]
    for index, context in enumerate(contexts, start=1):
        lines.append(f"{index}. {context}")
    return "\n".join(lines)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in value).strip("_") or "model"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay PersonaMem-v2 generator from a fixed context snapshot.")
    parser.add_argument("--context-snapshot", type=Path, required=True)
    parser.add_argument("--chat-model", required=True)
    parser.add_argument("--evaluator-model", default=settings.chat_model)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = asyncio.run(
        replay_generator_from_context_snapshot(
            load_json_file(args.context_snapshot),
            chat_model=args.chat_model,
            evaluator_model=args.evaluator_model,
            output_dir=args.output_dir,
        )
    )
    print(report["path"])


if __name__ == "__main__":
    main()
