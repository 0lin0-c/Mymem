# 🎯 检索策略基类
from abc import ABC, abstractmethod
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from tables import Resource, Category


class RetrievalStrategy(ABC):
    """检索策略抽象基类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 15,
    ) -> List[dict]:
        """
        执行检索

        Args:
            user_id: 用户ID
            query: 查询文本
            top_k: 返回数量

        Returns:
            List[dict]: 检索结果列表，每项包含 resource 和 score
        """
        pass

    @abstractmethod
    async def is_needed(self, context: str) -> bool:
        """
        判断是否需要使用此策略

        Args:
            context: 当前上下文

        Returns:
            bool: 是否需要
        """
        pass
