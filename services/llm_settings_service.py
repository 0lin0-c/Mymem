import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from repositories import CategoryRepository, UserRepository
from services.llm.user_llm_factory import UserLLMFactory

logger = logging.getLogger(__name__)


class LLMSettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def update_settings(
        self,
        user_id: str,
        llm_provider: str,
        llm_api_key: str,
        llm_base_url: str | None,
        llm_model: str,
    ) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False

        await self.user_repo.update(
            user_id,
            llm_provider=llm_provider,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_warmed_up=False,
        )
        await self.session.commit()

        UserLLMFactory.remove(user_id)
        asyncio.create_task(
            self._warmup_and_generate_categories(
                user_id,
                llm_provider,
                llm_api_key,
                llm_base_url,
                llm_model,
            )
        )
        return True

    async def get_settings(self, user_id: str) -> dict | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        return {
            "configured": bool(user.llm_provider and user.llm_api_key),
            "llm_provider": user.llm_provider,
            "llm_base_url": user.llm_base_url,
            "llm_model": user.llm_model,
            "warmed_up": user.llm_warmed_up,
        }

    @staticmethod
    async def _warmup_and_generate_categories(
        user_id: str,
        llm_provider: str,
        llm_api_key: str,
        llm_base_url: str | None,
        llm_model: str,
    ) -> None:
        try:
            llm = UserLLMFactory.get_or_create(
                user_id=user_id,
                provider=llm_provider,
                api_key=llm_api_key,
                base_url=llm_base_url,
                model=llm_model,
            )

            await llm.generate_chat_response(
                system_prompt="You are an assistant",
                context="",
                user_query="OK",
            )
            logger.info("User LLM warmup completed: user_id=%s", user_id)

            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                await user_repo.update(user_id, llm_warmed_up=True)
                await session.commit()

            async with AsyncSessionLocal() as session:
                category_repo = CategoryRepository(session)
                items = await category_repo.get_by_user_id(user_id)
                fixed_categories = {"核心自我", "情景时间轴", "语义知识库", "社交关系图谱"}
                has_real_categories = any(
                    "生成中" not in item.category_name
                    for item in items
                    if item.category_name not in fixed_categories
                )

                if not has_real_categories:
                    logger.info("User needs dynamic categories: user_id=%s", user_id)

        except Exception as exc:
            logger.error("User LLM warmup failed: user_id=%s error=%s", user_id, exc)
