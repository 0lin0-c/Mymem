from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from core.config import settings
from services.llm.base import BaseLLMProvider
from services.memory.writer import MemoryWriter
from tables.category import Category
from tables.resource import Resource


def _mock_llm(memory_intent: dict) -> AsyncMock:
    llm = AsyncMock(spec=BaseLLMProvider)
    llm.extract_memory_intent = AsyncMock(return_value=memory_intent)
    llm.get_embedding = AsyncMock(return_value=[0.1] * settings.embedding_dimensions)
    llm.count_tokens = AsyncMock(return_value=10)
    return llm


@pytest.mark.asyncio
async def test_save_chat_writes_resource_and_category_contract(db_session, test_user):
    llm = _mock_llm({
        "summary": "The user is interested in counseling.",
        "importance_score": 9,
        "response_summary": "Discussed counseling interests.",
        "atomic_items": [
            {
                "category_name": "Core Self",
                "content": "The user is interested in counseling.",
                "importance_score": 9,
                "memory_type": "profile_fact",
                "fact_type": "preference",
                "subject": "user",
                "source_role": "user",
                "confidence": 0.95,
                "extraction_origin": "direct_user_statement",
            }
        ],
    })
    writer = MemoryWriter(db_session, llm, enable_dedup=False)

    result = await writer.save_chat(
        user_id=test_user.id,
        user_input="I am interested in counseling.",
        assistant_response="That sounds meaningful.",
        modality="text",
    )
    await db_session.commit()

    resource = await db_session.get(Resource, result["resource_id"])
    categories = list((await db_session.execute(
        select(Category).where(Category.user_id == test_user.id)
    )).scalars().all())

    assert resource is not None
    assert resource.description == "The user is interested in counseling."
    assert resource.importance_score == 3
    assert len(categories) == 1
    assert categories[0].category_name == "Core Self"
    assert categories[0].content == "The user is interested in counseling."
    assert categories[0].importance_score == 3
    assert result["atomic_items"][0]["metadata"]["memory_type"] == "profile_fact"
    assert result["atomic_items"][0]["metadata"]["fact_type"] == "preference"
    assert result["atomic_items"][0]["metadata"]["source_role"] == "user"
    assert result["atomic_items"][0]["metadata"]["extraction_origin"] == "direct_user_statement"
    assert llm.extract_memory_intent.await_count >= 2
    assert llm.get_embedding.await_count >= 2


@pytest.mark.asyncio
async def test_save_chat_language_guard_drops_cjk_atomic_items_for_english_source(db_session, test_user):
    llm = _mock_llm({
        "summary": "用户对 counseling 感兴趣",
        "importance_score": 2,
        "response_summary": "助手进行了回应",
        "atomic_items": [
            {
                "category_name": "Core Self",
                "content": "用户对 counseling 感兴趣",
                "importance_score": 2,
            }
        ],
    })
    writer = MemoryWriter(db_session, llm, enable_dedup=False)

    result = await writer.save_chat(
        user_id=test_user.id,
        user_input="I am interested in counseling.",
        assistant_response="That sounds meaningful.",
        modality="text",
    )
    await db_session.commit()

    categories = list((await db_session.execute(
        select(Category).where(Category.user_id == test_user.id)
    )).scalars().all())
    resource = await db_session.get(Resource, result["resource_id"])

    assert result["language_guard"]["source_language"] == "en"
    assert result["language_guard"]["summary_replaced"] is True
    assert result["language_guard"]["response_summary_cleared"] is True
    assert result["language_guard"]["dropped_atomic_items"] == 1
    assert categories == []
    assert resource.description == "I am interested in counseling."


@pytest.mark.asyncio
async def test_save_chat_applies_temporary_evidence_quality_rules(db_session, test_user):
    llm = _mock_llm({
        "summary": "The user shared several memory candidates.",
        "importance_score": 2,
        "response_summary": "",
        "atomic_items": [
            {
                "category_name": "Core Self",
                "content": "The user had an appendectomy at age 6.",
                "importance_score": 3,
                "memory_type": "profile_fact",
                "fact_type": "health",
                "confidence": 0.95,
                "extraction_origin": "quoted_first_person",
            },
            {
                "category_name": "Core Self",
                "content": "The user values creative/resourceful solutions.",
                "importance_score": 3,
                "memory_type": "profile_fact",
                "fact_type": "value",
                "confidence": 0.90,
                "extraction_origin": "third_person_narrative",
            },
            {
                "category_name": "Core Self",
                "content": "The user may like thunderstorms.",
                "importance_score": 2,
                "memory_type": "profile_fact",
                "fact_type": "preference",
                "confidence": 0.40,
                "extraction_origin": "direct_user_statement",
            },
            {
                "category_name": "Core Self",
                "content": "The user prefers taking regular hydration breaks.",
                "importance_score": 2,
                "memory_type": "profile_fact",
                "fact_type": "preference",
                "confidence": 0.90,
                "extraction_origin": "assistant_advice",
            },
            {
                "category_name": "Episodic Memory",
                "content": "The user described witnessing a police incident through a narrative about Lena.",
                "importance_score": 3,
                "memory_type": "event_fact",
                "fact_type": "who_did_what",
                "confidence": 0.55,
                "extraction_origin": "third_person_narrative",
            },
            {
                "category_name": "Knowledge Base",
                "content": "The assistant suggested pacing and hydration strategies requested by the user.",
                "importance_score": 1,
                "memory_type": "advice_checklist",
                "fact_type": "checklist",
                "confidence": 0.85,
                "extraction_origin": "assistant_advice",
            },
        ],
    })
    writer = MemoryWriter(db_session, llm, enable_dedup=False)

    result = await writer.save_chat(
        user_id=test_user.id,
        user_input=(
            "Please translate this self-introduction: I had surgery because my tummy hurt. "
            "Also polish this Lena story about police lights."
        ),
        assistant_response="Here are pacing and hydration strategies.",
        modality="text",
    )
    await db_session.commit()

    categories = list((await db_session.execute(
        select(Category).where(Category.user_id == test_user.id)
    )).scalars().all())
    by_content = {category.content: category for category in categories}

    assert result["atomic_items_count"] == 3
    assert "The user had an appendectomy at age 6." in by_content
    assert by_content["The user had an appendectomy at age 6."].importance_score == 2
    assert "The user described witnessing a police incident through a narrative about Lena." in by_content
    assert by_content[
        "The user described witnessing a police incident through a narrative about Lena."
    ].importance_score == 1
    assert "The assistant suggested pacing and hydration strategies requested by the user." in by_content
    assert "The user values creative/resourceful solutions." not in by_content
    assert "The user may like thunderstorms." not in by_content
    assert "The user prefers taking regular hydration breaks." not in by_content
