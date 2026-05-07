from __future__ import annotations

import argparse
import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from repositories import CategoryRepository, ResourceRepository, UserRepository
from schemas.onboarding_schema import AICustomization, IdentityDetail, OnboardingRequest
from services.chat_orchestrator import ChatOrchestrator
from services.constants import BASE_CATEGORIES, LEGACY_TIMELINE_CATEGORY
from services.llm.factory import LLMFactory
from services.memory.writer import MemoryWriter
from services.profile_service import ProfileService
from services.retrieval.retriever import MemoryRetriever
from tables.category import Category
from tables.resource import Resource
from tables.resource_category import ResourceCategory
from tests.evals.converted_data.runner import (
    QAQuestion,
    _evaluate_storage_layer,
    _extract_retrieval_observation,
    _first_retrieved_rank,
    evaluate_answer_correctness,
    generate_answer_with_chat_orchestrator,
)
from tests.evals.personamem_v2.loader import (
    DEFAULT_SPLIT,
    PERSONAMEM_CACHE_DIR,
    build_samples,
    load_personamem_rows,
    save_rows_snapshot,
    snippet_to_turns,
)
from tests.evals.personamem_v2.models import (
    EvalMode,
    PersonaMemQuestion,
    PersonaMemReport,
    PersonaMemResult,
    PersonaMemSample,
)
from tests.evals.personamem_v2.reporting import save_analysis_markdown, save_results_json

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
OUTPUT_DIR = REPO_ROOT / "test_results" / "personamem_v2"


def _base_category_names() -> set[str]:
    return {category["name"] for category in BASE_CATEGORIES} | {LEGACY_TIMELINE_CATEGORY}


def _username_for_sample(sample: PersonaMemSample) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(sample.persona_id)).strip("_")
    return f"personamem_v2_persona_{suffix or 'unknown'}"


async def ensure_user_onboarded(
    session: AsyncSession,
    sample: PersonaMemSample,
    recreate_existing: bool = False,
) -> str:
    """Create a stable PersonaMem test user through the real onboarding service."""
    username = _username_for_sample(sample)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_username(username)
    if user and user.user_prompt_template and not recreate_existing:
        return user.id
    if user:
        await user_repo.delete(user.id)
        await session.commit()
        session.expire_all()

    persona_description = _build_persona_description(sample)
    request = OnboardingRequest(
        username=username,
        password="test_password",
        identity_type="other",
        identity_detail=IdentityDetail(description=persona_description),
        use_cases=["memory evaluation", "personalization benchmark"],
        interests=sample.interests or ["personalized assistant responses"],
        ai_customization=AICustomization(
            ai_name="Assistant",
            ai_role="friend",
            personality=["patient", "helpful"],
            communication_style="daily",
        ),
    )
    llm = LLMFactory.get_provider()
    service = ProfileService(session, llm)
    result = await service.onboarding(request)
    if not result.success:
        raise RuntimeError(f"PersonaMem onboarding failed for {username}: {result.message}")
    return result.user_id


def _build_persona_description(sample: PersonaMemSample) -> str:
    parts = []
    if sample.short_persona:
        parts.append(f"short_persona: {sample.short_persona}")
    if sample.expanded_persona:
        parts.append(f"expanded_persona: {sample.expanded_persona}")
    if not parts:
        return f"PersonaMem-v2 persona_id={sample.persona_id}"
    return "\n\n".join(parts)


async def _categories_for_prompt(session: AsyncSession, user_id: str) -> list[dict[str, str]]:
    category_repo = CategoryRepository(session)
    category_stats = await category_repo.get_category_stats(user_id)
    categories = list(BASE_CATEGORIES)
    for name in category_stats.keys():
        if name not in _base_category_names():
            categories.append(
                {"name": name, "description": f"User-specific memories related to {name}"}
            )
    return categories


async def _reset_user_memory(session: AsyncSession, user_id: str) -> None:
    await session.execute(
        delete(ResourceCategory).where(
            ResourceCategory.resource_id.in_(
                select(Resource.id).where(Resource.user_id == user_id)
            )
        )
    )
    await session.execute(delete(Category).where(Category.user_id == user_id))
    await session.execute(delete(Resource).where(Resource.user_id == user_id))
    await session.commit()


async def import_sample(
    session: AsyncSession,
    sample: PersonaMemSample,
    enable_dedup: bool = False,
    reset_memory: bool = False,
) -> tuple[str, int]:
    """Import PersonaMem snippets through MemoryWriter."""
    user_id = await ensure_user_onboarded(
        session,
        sample,
        recreate_existing=reset_memory,
    )
    if reset_memory:
        await _reset_user_memory(session, user_id)

    llm = LLMFactory.get_provider()
    writer = MemoryWriter(session, llm, enable_dedup=enable_dedup)
    categories = await _categories_for_prompt(session, user_id)
    memory_count = 0

    for question in sample.questions:
        for user_input, assistant_response in snippet_to_turns(question):
            try:
                await writer.save_chat(
                    user_id=user_id,
                    user_input=user_input,
                    assistant_response=assistant_response,
                    modality="text",
                    user_categories=categories,
                )
                memory_count += 1
                if memory_count % 10 == 0:
                    await session.commit()
            except Exception:
                logger.exception(
                    "Failed to import PersonaMem snippet: persona_id=%s row_index=%s",
                    question.persona_id,
                    question.row_index,
                )
                await session.rollback()

    await session.commit()
    return user_id, memory_count


async def resolve_existing_user(session: AsyncSession, sample: PersonaMemSample) -> tuple[str, int] | None:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_username(_username_for_sample(sample))
    if not user:
        return None
    resource_repo = ResourceRepository(session)
    memory_count = len(await resource_repo.get_by_user_id(user.id))
    return user.id, memory_count


async def evaluate_sample(
    session: AsyncSession,
    sample: PersonaMemSample,
    user_id: str,
    memory_count: int,
    sample_index: int,
    eval_mode: EvalMode,
    top_k: int = 10,
) -> PersonaMemReport:
    llm = LLMFactory.get_provider()
    retriever = MemoryRetriever(session, llm)
    user = await UserRepository(session).get_by_id(user_id)
    results: list[PersonaMemResult] = []

    for question in sample.questions:
        result = _make_result(question, eval_mode)
        try:
            qa_question = _to_converted_qa(question)
            storage_trace = await _evaluate_storage_layer(session, user_id, qa_question)
            result.storage_hit = storage_trace["storage_hit"]
            result.evaluation_trace["storage_eval"] = storage_trace

            if eval_mode == EvalMode.STORAGE:
                result.is_correct = result.storage_hit
                result.correctness_explanation = (
                    "Storage evidence found in DB."
                    if result.storage_hit
                    else "No DB evidence found for expected PersonaMem answer or evidence."
                )
            else:
                retrieved = await retriever.retrieve(
                    user_id=user_id,
                    query=question.question,
                    top_k=top_k,
                    use_llm_classification=True,
                    track_access=False,
                )
                contexts, scores, layer_info = _extract_retrieval_observation(retrieved)
                result.retrieved_contexts = contexts
                result.retrieved_scores = scores
                result.retrieval_layer = layer_info
                result.rank_position = _first_retrieved_rank(
                    storage_trace.get("db_memories_sample", []),
                    contexts,
                )
                result.retrieval_hit = result.rank_position is not None

                if eval_mode == EvalMode.RETRIEVAL:
                    result.is_correct = result.retrieval_hit
                    result.correctness_explanation = (
                        f"DB evidence retrieved at rank {result.rank_position}."
                        if result.retrieval_hit
                        else "DB evidence exists but did not appear in retrieved top-k."
                    )
                elif contexts:
                    result.llm_answer = await generate_answer_with_chat_orchestrator(
                        session=session,
                        llm=llm,
                        user=user,
                        user_id=user_id,
                        question=question.question,
                        top_k=top_k,
                        retrieved_results=retrieved,
                    )
                    result.is_correct, result.correctness_explanation = (
                        await evaluate_answer_correctness(
                            llm,
                            question.question,
                            result.llm_answer,
                            question.answer,
                        )
                    )
                else:
                    result.is_correct = False
                    result.correctness_explanation = (
                        "No retrieved context available for assistant answer generation."
                    )
        except Exception as exc:
            logger.exception(
                "PersonaMem evaluation failed: persona_id=%s row_index=%s",
                question.persona_id,
                question.row_index,
            )
            result.error = str(exc)

        results.append(result)

    return PersonaMemReport(
        sample_index=sample_index,
        character=sample.persona_id,
        user_id=user_id,
        total_sessions=sample.total_questions,
        total_memories=memory_count,
        total_questions=sample.total_questions,
        results=results,
    )


async def run_personamem_v2_eval(
    split: str = DEFAULT_SPLIT,
    max_personas: int = 2,
    max_questions: int = 5,
    max_rows: int | None = 100,
    persona_id: str | None = None,
    import_only: bool = False,
    retrieval_only: bool = False,
    enable_dedup: bool = False,
    reset_memory: bool = False,
    eval_mode: EvalMode = EvalMode.ASSISTANT,
    top_k: int = 10,
    save_raw_snapshot: bool = True,
    download_only: bool = False,
) -> list[PersonaMemReport]:
    rows = load_personamem_rows(
        split=split,
        max_rows=max_rows,
        cache_dir=PERSONAMEM_CACHE_DIR,
    )
    if save_raw_snapshot:
        save_rows_snapshot(rows, split=split)
    samples = build_samples(
        rows,
        split=split,
        max_personas=max_personas,
        max_questions=max_questions,
        persona_id=persona_id,
    )
    if download_only:
        logger.info(
            "PersonaMem-v2 download-only complete: rows=%s samples=%s cache=%s",
            len(rows),
            len(samples),
            PERSONAMEM_CACHE_DIR,
        )
        return []

    reports: list[PersonaMemReport] = []

    async with AsyncSessionLocal() as session:
        for sample_index, sample in enumerate(samples):
            if retrieval_only:
                resolved = await resolve_existing_user(session, sample)
                if not resolved:
                    logger.error(
                        "PersonaMem user does not exist for retrieval-only mode: %s",
                        _username_for_sample(sample),
                    )
                    continue
                user_id, memory_count = resolved
            else:
                user_id, memory_count = await import_sample(
                    session=session,
                    sample=sample,
                    enable_dedup=enable_dedup,
                    reset_memory=reset_memory,
                )

            if import_only:
                continue

            reports.append(
                await evaluate_sample(
                    session=session,
                    sample=sample,
                    user_id=user_id,
                    memory_count=memory_count,
                    sample_index=sample_index,
                    eval_mode=eval_mode,
                    top_k=top_k,
                )
            )

    if reports:
        results_path = save_results_json(reports, OUTPUT_DIR, eval_mode=eval_mode.value)
        logger.info("PersonaMem-v2 results saved to %s", results_path)
        analysis_path = save_analysis_markdown(results_path)
        if analysis_path:
            logger.info("PersonaMem-v2 analysis saved to %s", analysis_path)
    return reports


def _make_result(question: PersonaMemQuestion, eval_mode: EvalMode) -> PersonaMemResult:
    return PersonaMemResult(
        question=question.question,
        expected_answer=question.answer,
        persona_id=question.persona_id,
        eval_mode=eval_mode.value,
        evidence=question.evidence,
        incorrect_answers=question.incorrect_answers,
        preference=question.preference,
        related_conversation_snippet=question.related_conversation_snippet,
        pref_type=question.pref_type,
        who=question.who,
        updated=question.updated,
        source_split=question.source_split,
        row_index=question.row_index,
    )


def _to_converted_qa(question: PersonaMemQuestion) -> QAQuestion:
    return QAQuestion(
        question=question.question,
        answer=question.answer,
        category=0,
        evidence=question.evidence,
        target_character=question.persona_id,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run PersonaMem-v2 text snippet eval.")
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--max-personas", type=int, default=2)
    parser.add_argument("--max-questions", type=int, default=5)
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--persona-id", type=str)
    parser.add_argument(
        "--eval-mode",
        choices=[mode.value for mode in EvalMode],
        default=EvalMode.ASSISTANT.value,
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--import-only", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--reset-memory", action="store_true")
    parser.add_argument("--no-dedup", action="store_true")
    parser.add_argument("--no-save-raw-snapshot", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        run_personamem_v2_eval(
            split=args.split,
            max_personas=args.max_personas,
            max_questions=args.max_questions,
            max_rows=args.max_rows,
            persona_id=args.persona_id,
            import_only=args.import_only,
            retrieval_only=args.retrieval_only,
            enable_dedup=not args.no_dedup,
            reset_memory=args.reset_memory,
            eval_mode=EvalMode(args.eval_mode),
            top_k=args.top_k,
            save_raw_snapshot=not args.no_save_raw_snapshot,
            download_only=args.download_only,
        )
    )


if __name__ == "__main__":
    main()
