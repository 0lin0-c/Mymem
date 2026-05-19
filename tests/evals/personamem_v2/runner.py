from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.config import settings
from repositories import CategoryRepository, ResourceRepository, UserRepository
from schemas.onboarding_schema import AICustomization, IdentityDetail, OnboardingRequest
from services.chat_orchestrator import ChatOrchestrator
from services.constants import BASE_CATEGORIES, LEGACY_TIMELINE_CATEGORY
from services.llm.factory import LLMFactory
from services.memory.writer import MemoryWriter
from services.profile_service import ProfileService
from services.retrieval.retriever import MemoryRetriever
from services.retrieval.scoring_config import DEFAULT_RETRIEVAL_SCORING_CONFIG
from tables.category import Category
from tables.resource import Resource
from tables.resource_category import ResourceCategory
from tests.evals.common import build_run_manifest, default_scoring_config_payload
from tests.evals.converted_data.runner import (
    QAQuestion,
    _evaluate_storage_layer,
    _extract_retrieval_observation,
    _first_retrieved_rank,
    evaluate_answer_correctness,
    generate_answer_with_chat_orchestrator,
)
from tests.evals.converted_data.metrics import calculate_metrics
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
from tests.evals.personamem_v2.analysis import analyze_personamem_evidence
from tests.evals.personamem_v2.reporting import (
    build_model_sweep_ranking_key,
    build_paired_comparison,
    build_personamem_statistics_from_qa_results,
    determine_experiment_conclusion,
    save_analysis_markdown,
    save_results_json,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
OUTPUT_DIR = REPO_ROOT / "test_results" / "personamem_v2"
DEFAULT_MODEL_SWEEP = [
    "GLM-5-Turbo",
    "GLM-5",
    "GLM-5.1",
    "Qwen3.5-Plus",
    "DeepSeek-V4-Pro",
]
MODEL_SWEEP_DIAGNOSTIC_REASON = (
    "legacy_model_sweep_changes_writer_retrieval_classifier_and_generator; "
    "use personamem_v2_orthogonal generator_ab or writer_ab for formal A/B"
)


def _base_category_names() -> set[str]:
    return {category["name"] for category in BASE_CATEGORIES} | {LEGACY_TIMELINE_CATEGORY}


def parse_model_sweep(value: str | None) -> list[str]:
    if value is None:
        return []
    if value.strip().lower() in {"default", "all"}:
        return list(DEFAULT_MODEL_SWEEP)
    return [item.strip() for item in value.split(",") if item.strip()]


def _safe_username_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]+", "_", value).strip("_")


def _username_for_sample(sample: PersonaMemSample, chat_model: str | None = None) -> str:
    suffix = _safe_username_part(str(sample.persona_id)) or "unknown"
    if chat_model:
        model_part = _safe_username_part(chat_model)
        return f"{model_part}-persona{suffix}"
    return f"personamem_v2_persona_{suffix}"


async def ensure_user_onboarded(
    session: AsyncSession,
    sample: PersonaMemSample,
    recreate_existing: bool = False,
    chat_model: str | None = None,
) -> str:
    """Create a stable PersonaMem test user through the real onboarding service."""
    username = _username_for_sample(sample, chat_model=chat_model)
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
    chat_model: str | None = None,
) -> tuple[str, int]:
    """Import PersonaMem snippets through MemoryWriter."""
    user_id = await ensure_user_onboarded(
        session,
        sample,
        recreate_existing=reset_memory,
        chat_model=chat_model,
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


async def resolve_existing_user(
    session: AsyncSession,
    sample: PersonaMemSample,
    chat_model: str | None = None,
) -> tuple[str, int] | None:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_username(_username_for_sample(sample, chat_model=chat_model))
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
    chat_model: str | None = None,
    evaluator_model: str | None = None,
    default_evaluator_model: str | None = None,
) -> PersonaMemReport:
    active_chat_model = chat_model or settings.chat_model
    resolved_evaluator_model, evaluator_isolated = _resolve_evaluator_model(
        active_chat_model=active_chat_model,
        evaluator_model=evaluator_model,
        default_evaluator_model=default_evaluator_model,
    )
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
                    evaluator_llm = _get_provider_for_model(resolved_evaluator_model)
                    result.is_correct, result.correctness_explanation = (
                        await evaluate_answer_correctness(
                            evaluator_llm,
                            question.question,
                            result.llm_answer,
                            question.answer,
                        )
                    )
                    result.evaluation_trace["evaluator"] = {
                        "model": resolved_evaluator_model,
                        "isolated": evaluator_isolated,
                    }
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
        chat_model=active_chat_model,
        evaluator_model=resolved_evaluator_model,
        evaluator_isolated=evaluator_isolated,
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
    chat_model: str | None = None,
    evaluator_model: str | None = None,
    default_evaluator_model: str | None = None,
) -> list[PersonaMemReport]:
    active_chat_model = chat_model or settings.chat_model
    resolved_evaluator_model, evaluator_isolated = _resolve_evaluator_model(
        active_chat_model=active_chat_model,
        evaluator_model=evaluator_model,
        default_evaluator_model=default_evaluator_model,
    )
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
                resolved = await resolve_existing_user(session, sample, chat_model=chat_model)
                if not resolved:
                    logger.error(
                        "PersonaMem user does not exist for retrieval-only mode: %s",
                        _username_for_sample(sample, chat_model=chat_model),
                    )
                    continue
                user_id, memory_count = resolved
            else:
                user_id, memory_count = await import_sample(
                    session=session,
                    sample=sample,
                    enable_dedup=enable_dedup,
                    reset_memory=reset_memory,
                    chat_model=chat_model,
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
                    chat_model=active_chat_model,
                    evaluator_model=evaluator_model,
                    default_evaluator_model=default_evaluator_model,
                )
            )

    if reports:
        run_manifest = build_run_manifest(
            harness="personamem_v2",
            eval_mode=eval_mode.value,
            dataset="bowen-upenn/PersonaMem-v2",
            split=split,
            persona_id=persona_id,
            question_count=sum(report.total_questions for report in reports),
            import_only=import_only,
            retrieval_only=retrieval_only,
            reset_memory=reset_memory,
            chat_model=active_chat_model,
            evaluator_model=resolved_evaluator_model,
            evaluator_isolated=evaluator_isolated,
            top_k=top_k,
            scoring_config=default_scoring_config_payload(),
            rerank_config=None,
        )
        results_path = save_results_json(
            reports,
            OUTPUT_DIR,
            eval_mode=eval_mode.value,
            test_info={
                "chat_model": active_chat_model,
                "evaluator_model": resolved_evaluator_model,
                "evaluator_isolated": evaluator_isolated,
                "top_k": top_k,
                "scoring_config": default_scoring_config_payload(),
                "rerank_config": None,
            },
            run_manifest=run_manifest,
        )
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


def _set_chat_model(chat_model: str) -> None:
    settings.chat_model = chat_model
    LLMFactory.reset()
    logger.info("PersonaMem-v2 model sweep using CHAT_MODEL=%s", chat_model)


@contextlib.contextmanager
def _temporary_chat_model(chat_model: str):
    original_chat_model = settings.chat_model
    try:
        if chat_model != original_chat_model:
            settings.chat_model = chat_model
            LLMFactory.reset()
        yield
    finally:
        if settings.chat_model != original_chat_model:
            settings.chat_model = original_chat_model
            LLMFactory.reset()


def _resolve_evaluator_model(
    *,
    active_chat_model: str,
    evaluator_model: str | None,
    default_evaluator_model: str | None = None,
) -> tuple[str, bool]:
    if evaluator_model:
        return evaluator_model, True
    if default_evaluator_model:
        return default_evaluator_model, False
    return active_chat_model, False


def _get_provider_for_model(chat_model: str):
    if chat_model == settings.chat_model:
        return LLMFactory.get_provider()
    with _temporary_chat_model(chat_model):
        return LLMFactory.get_provider()


def _build_stage_payload(
    result: PersonaMemResult,
    *,
    stage: str,
    include_generated: bool = False,
) -> dict[str, Any]:
    return analyze_personamem_evidence(
        question=result.question,
        correct_answer=result.expected_answer,
        supporting_preference=result.preference,
        related_conversation_snippet=result.related_conversation_snippet,
        incorrect_answers=result.incorrect_answers,
        contexts=result.retrieved_contexts,
        scores=result.retrieved_scores,
        stage=stage,
        loose_rank_position=result.rank_position,
        retrieval_hit_loose=result.retrieval_hit,
        generated_answer=result.llm_answer if include_generated else None,
        is_correct=result.is_correct if include_generated else None,
    )


def _build_personamem_metrics_for_reports(
    reports: list[PersonaMemReport],
    overall_metrics: dict[str, Any],
) -> dict[str, Any]:
    qa_results: list[dict[str, Any]] = []
    for report in reports:
        for result in report.results:
            qa_results.append(
                {
                    "persona_id": result.persona_id,
                    "source_split": result.source_split,
                    "row_index": result.row_index,
                    "question": result.question,
                    "is_correct": result.is_correct,
                    "retrieval_stage": _build_stage_payload(result, stage="retrieval_top_k"),
                    "answer_stage": _build_stage_payload(
                        result,
                        stage="answer_context",
                        include_generated=True,
                    ),
                }
            )
    return build_personamem_statistics_from_qa_results(qa_results, overall_metrics)


def _build_comparison_items_for_reports(reports: list[PersonaMemReport]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for report in reports:
        for result in report.results:
            items.append(
                {
                    "persona_id": result.persona_id,
                    "source_split": result.source_split,
                    "row_index": result.row_index,
                    "question": result.question,
                    "is_correct": result.is_correct,
                    "retrieval_stage": _build_stage_payload(result, stage="retrieval_top_k"),
                }
            )
    return items


async def run_personamem_v2_model_sweep(
    chat_models: list[str],
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
    evaluator_model: str | None = None,
) -> dict[str, Any]:
    """Run the same PersonaMem-v2 flow once per chat model with isolated users."""
    original_chat_model = settings.chat_model
    default_evaluator_model = evaluator_model or original_chat_model
    sweep_results: list[dict[str, Any]] = []
    try:
        for chat_model in chat_models:
            _set_chat_model(chat_model)
            reports = await run_personamem_v2_eval(
                split=split,
                max_personas=max_personas,
                max_questions=max_questions,
                max_rows=max_rows,
                persona_id=persona_id,
                import_only=import_only,
                retrieval_only=retrieval_only,
                enable_dedup=enable_dedup,
                reset_memory=reset_memory,
                eval_mode=eval_mode,
                top_k=top_k,
                save_raw_snapshot=save_raw_snapshot,
                download_only=download_only,
                chat_model=chat_model,
                evaluator_model=evaluator_model,
                default_evaluator_model=default_evaluator_model,
            )
            all_results = [result for report in reports for result in report.results]
            metrics = calculate_metrics(all_results, eval_mode=eval_mode.value) if all_results else {}
            personamem_metrics = _build_personamem_metrics_for_reports(reports, metrics)
            sweep_results.append(
                {
                    "chat_model": chat_model,
                    "usernames": [
                        _username_for_sample(
                            PersonaMemSample(persona_id=report.character, user_key=""),
                            chat_model=chat_model,
                        )
                        for report in reports
                    ],
                    "user_ids": [report.user_id for report in reports],
                    "total_memories": sum(report.total_memories for report in reports),
                    "total_questions": sum(report.total_questions for report in reports),
                    "metrics": metrics,
                    "personamem_metrics": personamem_metrics,
                    "comparison_items": _build_comparison_items_for_reports(reports),
                    "evaluator_model": reports[0].evaluator_model if reports else evaluator_model,
                    "evaluator_isolated": reports[0].evaluator_isolated if reports else bool(evaluator_model),
                }
            )
    finally:
        settings.chat_model = original_chat_model
        LLMFactory.reset()

    if not import_only and sweep_results:
        return save_model_sweep_summary(
            sweep_results=sweep_results,
            eval_mode=eval_mode.value,
            output_dir=OUTPUT_DIR,
            split=split,
            persona_id=persona_id,
            top_k=top_k,
            retrieval_only=retrieval_only,
            import_only=import_only,
            reset_memory=reset_memory,
        )
    return {"results": sweep_results}


def save_model_sweep_summary(
    sweep_results: list[dict[str, Any]],
    eval_mode: str,
    output_dir: Path = OUTPUT_DIR,
    *,
    split: str | None = None,
    persona_id: str | None = None,
    top_k: int | None = None,
    retrieval_only: bool | None = None,
    import_only: bool | None = None,
    reset_memory: bool | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ranked = sorted(sweep_results, key=build_model_sweep_ranking_key, reverse=True)
    baseline = sweep_results[0] if sweep_results else None
    leader = ranked[0] if ranked else None
    pairwise_comparisons = []
    if baseline:
        for candidate in sweep_results[1:]:
            paired = build_paired_comparison(
                baseline.get("comparison_items") or [],
                candidate.get("comparison_items") or [],
            )
            pairwise_comparisons.append(
                {
                    "baseline_model": baseline["chat_model"],
                    "candidate_model": candidate["chat_model"],
                    "changed_variables": ["chat_model", "writer", "retrieval_classifier", "generator"],
                    "formal_ab_eligible": False,
                    "diagnostic_reason": MODEL_SWEEP_DIAGNOSTIC_REASON,
                    "paired_comparison": paired,
                    "diagnostic_conclusion": determine_experiment_conclusion(
                        paired,
                        changed_variables=["chat_model", "writer", "retrieval_classifier", "generator"],
                    ),
                    "conclusion": "diagnostic_only",
                }
            )
    evaluator_model = leader.get("evaluator_model") if leader else None
    evaluator_isolated = leader.get("evaluator_isolated") if leader else None
    payload = {
        "test_info": {
            "timestamp": timestamp,
            "dataset": "bowen-upenn/PersonaMem-v2",
            "harness": "personamem_v2_legacy_model_sweep_diagnostic",
            "eval_mode": eval_mode,
            "evaluator_model": evaluator_model,
            "evaluator_isolated": evaluator_isolated,
        },
        "ranked_models": ranked,
        "pairwise_comparisons": pairwise_comparisons,
        "experiment_conclusion": "diagnostic_only",
        "formal_ab_eligible": False,
        "diagnostic_reason": MODEL_SWEEP_DIAGNOSTIC_REASON,
        "run_manifest": build_run_manifest(
            harness="personamem_v2_legacy_model_sweep_diagnostic",
            eval_mode=eval_mode,
            dataset="bowen-upenn/PersonaMem-v2",
            split=split,
            persona_id=persona_id,
            question_count=max((item.get("total_questions", 0) for item in ranked), default=None),
            import_only=import_only,
            retrieval_only=retrieval_only,
            reset_memory=reset_memory,
            chat_model="model_sweep",
            evaluator_model=evaluator_model,
            evaluator_isolated=evaluator_isolated,
            top_k=top_k,
            scoring_config=DEFAULT_RETRIEVAL_SCORING_CONFIG.sql_params(),
            rerank_config=None,
            extra={
                "formal_ab_eligible": False,
                "diagnostic_reason": MODEL_SWEEP_DIAGNOSTIC_REASON,
            },
        ),
    }
    json_path = output_dir / f"personamem_v2_{eval_mode}_model_sweep_{timestamp}.json"
    markdown_path = output_dir / f"personamem_v2_{eval_mode}_model_sweep_{timestamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_model_sweep_markdown(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def _render_model_sweep_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# PersonaMem-v2 Model Sweep Diagnostic",
        "",
        "This legacy report is diagnostic only and must not be used as a formal A/B decision.",
        "",
        f"- eval_mode: {payload['test_info']['eval_mode']}",
        f"- timestamp: {payload['test_info']['timestamp']}",
        f"- evaluator_model: {payload['test_info'].get('evaluator_model')}",
        f"- evaluator_isolated: {payload['test_info'].get('evaluator_isolated')}",
        f"- experiment_conclusion: `{payload.get('experiment_conclusion')}`",
        f"- formal_ab_eligible: `{payload.get('formal_ab_eligible')}`",
        f"- diagnostic_reason: `{payload.get('diagnostic_reason')}`",
        "",
        "| Rank | CHAT_MODEL | Accuracy | Total Questions | Total Memories | Username |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for index, item in enumerate(payload["ranked_models"], 1):
        metrics = item.get("metrics", {})
        accuracy = metrics.get("accuracy", metrics.get("answer_accuracy", 0))
        usernames = ", ".join(item.get("usernames") or [])
        evidence_summary = (
            item.get("personamem_metrics", {})
            .get("personamem_evidence", {})
            .get("evidence_first_summary", {})
        )
        primary_metrics = evidence_summary.get("primary_metrics") or {}
        labels = ", ".join(evidence_summary.get("diagnostic_labels") or []) or "-"
        lines.append(
            f"| {index} | `{item['chat_model']}` | {accuracy} | "
            f"{item.get('total_questions', 0)} | {item.get('total_memories', 0)} | `{usernames}` |"
        )
        lines.append(
            f"|  | evidence | answerable@k={primary_metrics.get('answerable_context_hit_at_k', 0):.2f}% | "
            f"pref@k={primary_metrics.get('target_preference_hit_at_k', 0):.2f}% | "
            f"anchor@k={primary_metrics.get('target_answer_anchor_hit_at_k', 0):.2f}% | "
            f"wrong-neighbor={primary_metrics.get('wrong_neighbor_substitution_rate', 0):.2f}% | "
            f"not-retrieved={primary_metrics.get('target_evidence_not_retrieved_rate', 0):.2f}% | "
            f"`{labels}` |"
        )
    if payload.get("pairwise_comparisons"):
        lines.extend(["", "## Pairwise Comparisons"])
        for item in payload["pairwise_comparisons"]:
            paired = item["paired_comparison"]
            lines.append(
                f"- `{item['candidate_model']}` vs `{item['baseline_model']}`: "
                f"gain={paired['gain']}, regression={paired['regression']}, "
                f"stable_success={paired['stable_success']}, stable_failure={paired['stable_failure']}, "
                f"retrieval_changed_answer_same={paired['retrieval_changed_answer_same']}, "
                f"retrieval_same_answer_changed={paired['retrieval_same_answer_changed']}, "
                f"formal_ab_eligible=`{item.get('formal_ab_eligible')}`, "
                f"conclusion=`{item['conclusion']}`"
            )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--evaluator-model",
        type=str,
        help="Optional fixed evaluator model used only for answer correctness judging.",
    )
    parser.add_argument(
        "--personamem-v2-evaluator-model",
        dest="evaluator_model",
        type=str,
        help="Alias for --evaluator-model; matches the pytest option name.",
    )
    parser.add_argument(
        "--model-sweep",
        type=str,
        help=(
            "Comma-separated CHAT_MODEL list, or 'default' for "
            "GLM-5-Turbo, GLM-5, GLM-5.1, Qwen3.5-Plus, DeepSeek-V4-Pro."
        ),
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = build_arg_parser()
    args = parser.parse_args()

    model_sweep = parse_model_sweep(args.model_sweep)
    if model_sweep:
        result = asyncio.run(
            run_personamem_v2_model_sweep(
                chat_models=model_sweep,
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
                evaluator_model=args.evaluator_model,
            )
        )
        if result.get("json_path"):
            print(f"model_sweep_json={result['json_path']}")
        if result.get("markdown_path"):
            print(f"model_sweep_markdown={result['markdown_path']}")
        return

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
            evaluator_model=args.evaluator_model,
        )
    )


if __name__ == "__main__":
    main()
