# 👤 用户 Repository：封装用户相关的数据库操作
import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tables.user import User
from repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """用户数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        """通过用户名查找用户"""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if user:
            logger.debug(f"查找到用户: username={username}, id={user.id}")
        return user

    async def create(
        self,
        username: str,
        password: str,
        user_prompt_template: str | None = None,
        agent_persona_template: str | None = None,
    ) -> User:
        """创建新用户"""
        user = await super().create(
            id=str(uuid.uuid4()),
            username=username,
            password=password,
            user_prompt_template=user_prompt_template,
            agent_persona_template=agent_persona_template,
        )
        logger.info(f"创建用户: id={user.id}, username={username}")
        return user

    async def update_templates(
        self,
        user_id: str,
        user_prompt_template: str | None = None,
        agent_persona_template: str | None = None,
    ) -> User | None:
        """更新用户的角色模板"""
        updates = {}
        if user_prompt_template is not None:
            updates["user_prompt_template"] = user_prompt_template
        if agent_persona_template is not None:
            updates["agent_persona_template"] = agent_persona_template

        if not updates:
            return await self.get_by_id(user_id)

        return await self.update(user_id, **updates)

    async def update_password(self, user_id: str, new_password_hash: str) -> User | None:
        """更新用户密码"""
        return await self.update(user_id, password=new_password_hash)
