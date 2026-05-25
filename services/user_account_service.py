import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from repositories import UserRepository
from services.llm.factory import LLMFactory
from services.llm.user_llm_factory import UserLLMFactory
from services.session import session_manager

logger = logging.getLogger(__name__)


class UserAccountService:
    def __init__(self, session: AsyncSession | None):
        self.user_repo = UserRepository(session) if session is not None else None

    async def login(self, username: str, password: str) -> dict:
        if self.user_repo is None:
            raise RuntimeError("User repository is required for login")
        user = await self.user_repo.get_by_username(username)
        if not user:
            logger.warning("Login failed: user not found, username=%s", username)
            return {"success": False, "message": "用户不存在"}

        if user.password != password:
            logger.warning("Login failed: bad password, username=%s", username)
            return {"success": False, "message": "密码错误"}

        ai_name = None
        if user.agent_persona_template:
            match = re.search(r"你是([^，。、\s]+)", user.agent_persona_template)
            if match:
                ai_name = match.group(1)

        logger.info("Login succeeded: username=%s, user_id=%s", username, user.id)
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "ai_name": ai_name,
            "llm_configured": bool(user.llm_provider and user.llm_api_key),
            "message": "登录成功",
        }

    async def get_user(self, user_id: str | None):
        if not user_id:
            return None
        if self.user_repo is None:
            raise RuntimeError("User repository is required for user lookup")
        return await self.user_repo.get_by_id(user_id)

    async def get_user_llm_context(self, user_id: str | None) -> tuple[object | None, object | None]:
        if not user_id:
            return None, LLMFactory.get_provider()

        user = await self.get_user(user_id)
        if not user:
            return None, None

        if user.llm_provider and user.llm_api_key:
            llm = UserLLMFactory.get_or_create(
                user_id=user.id,
                provider=user.llm_provider,
                api_key=user.llm_api_key,
                base_url=user.llm_base_url,
                model=user.llm_model,
            )
        else:
            llm = LLMFactory.get_provider()
        return user, llm

    def logout(self, user_id: str, session_id: str | None = None) -> None:
        if session_id:
            session_manager.destroy_session(session_id)
            logger.info("Session destroyed: session_id=%s", session_id)

        UserLLMFactory.remove(user_id)
        logger.info("User LLM client cache cleared: user_id=%s", user_id)
