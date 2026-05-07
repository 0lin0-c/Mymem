from unittest.mock import AsyncMock, MagicMock

import pytest

from services.retrieval.retriever import MemoryRetriever


class TestSufficiencyCheck:
    @pytest.mark.asyncio
    async def test_check_sufficiency_prompt_no_longer_prefers_sufficient(self, db_session):
        mock_llm = MagicMock()
        mock_llm.generate_chat_response = AsyncMock(
            return_value='{"sufficient": false, "reason": "Need exact date."}'
        )
        retriever = MemoryRetriever(db_session, mock_llm)

        category = MagicMock()
        category.category_name = "Timeline"
        category.content = "User joined an activist group in February 2026."

        result = await retriever._check_sufficiency(
            "When did Caroline go to the LGBTQ support group?",
            [{"category": category, "score": 0.42}],
        )

        assert result is False
        prompt = mock_llm.generate_chat_response.await_args.kwargs["user_query"]
        assert 'Prefer "Sufficient" judgment to avoid over-retrieval' not in prompt
        assert "prefer Insufficient" in prompt
        assert "exact fact is explicitly present" in prompt

    @pytest.mark.asyncio
    async def test_check_sufficiency_fallback_does_not_use_result_count(self, db_session):
        mock_llm = MagicMock()
        mock_llm.generate_chat_response = AsyncMock(side_effect=RuntimeError("llm failed"))
        retriever = MemoryRetriever(db_session, mock_llm)

        category = MagicMock()
        category.category_name = "Timeline"
        category.content = "Partial timeline memory."

        result = await retriever._check_sufficiency(
            "When did Caroline go to the LGBTQ support group?",
            [
                {"category": category, "score": 0.20},
                {"category": category, "score": 0.18},
                {"category": category, "score": 0.15},
            ],
        )

        assert result is False
