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
    llm.extract_memory_intent.assert_awaited_once()
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

