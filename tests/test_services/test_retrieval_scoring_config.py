from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.retrieval.scoring_config import DEFAULT_RETRIEVAL_SCORING_CONFIG
from services.retrieval.retriever import MemoryRetriever


def test_default_retrieval_scoring_config_prefers_similarity_over_recency():
    assert DEFAULT_RETRIEVAL_SCORING_CONFIG.similarity_power == 2.0
    assert DEFAULT_RETRIEVAL_SCORING_CONFIG.recency_power == 0.5
    assert DEFAULT_RETRIEVAL_SCORING_CONFIG.access_power == 1.0
    assert DEFAULT_RETRIEVAL_SCORING_CONFIG.importance_power == 1.0


def test_low_confidence_fallback_marks_small_candidate_set():
    retriever = object.__new__(MemoryRetriever)
    candidates = [
        {"resource": object(), "score": 0.02, "strategy": "vector"},
        {"resource": object(), "score": 0.01, "strategy": "vector"},
        {"resource": object(), "score": 0.005, "strategy": "vector"},
        {"resource": object(), "score": 0.001, "strategy": "vector"},
    ]

    fallback = retriever._low_confidence_fallback(candidates, top_k=10)

    assert len(fallback) == 3
    assert all(item["low_confidence_fallback"] is True for item in fallback)
    assert [item["score"] for item in fallback] == [0.02, 0.01, 0.005]


@pytest.mark.asyncio
async def test_retrieve_track_access_false_skips_access_increment():
    retriever = object.__new__(MemoryRetriever)
    retriever.vector_strategy = SimpleNamespace(
        search=AsyncMock(return_value=[
            {
                "resource": SimpleNamespace(id="r1", importance_score=2, access_count=0),
                "score": 0.5,
                "strategy": "vector",
            }
        ])
    )
    retriever._increment_access_counts = AsyncMock()

    results = await retriever.retrieve(
        user_id="user-1",
        query="test",
        use_llm_classification=False,
        track_access=False,
    )

    assert len(results) == 1
    retriever._increment_access_counts.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_track_access_true_keeps_default_increment():
    retriever = object.__new__(MemoryRetriever)
    retriever.vector_strategy = SimpleNamespace(
        search=AsyncMock(return_value=[
            {
                "resource": SimpleNamespace(id="r1", importance_score=2, access_count=0),
                "score": 0.5,
                "strategy": "vector",
            }
        ])
    )
    retriever._increment_access_counts = AsyncMock()

    await retriever.retrieve(
        user_id="user-1",
        query="test",
        use_llm_classification=False,
    )

    retriever._increment_access_counts.assert_awaited_once()
