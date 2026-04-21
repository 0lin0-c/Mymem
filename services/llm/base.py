# 📜 抽象基类：强制定义所有模型必须具备的方法
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Any


class BaseLLMProvider(ABC):
    """大模型提供商抽象基类

    所有模型提供商必须实现以下方法：
    1. generate_chat_response - 生成对话回复
    2. get_embedding - 文本转向量
    3. extract_memory_intent - 提取记忆意图
    4. count_tokens - Token 计数
    5. generate_stream_response - 流式输出（可选）
    """

    @abstractmethod
    async def generate_chat_response(
        self,
        system_prompt: str,
        context: str,
        user_query: str,
    ) -> str:
        """生成对话回复

        Args:
            system_prompt: 系统设定
            context: 检索到的记忆上下文
            user_query: 用户当前提问

        Returns:
            str: 纯文本回答
        """
        pass

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """文本转向量

        Args:
            text: 需要向量化的文本

        Returns:
            List[float]: 浮点数数组，长度为 embedding_dimensions
        """
        pass

    @abstractmethod
    async def extract_memory_intent(
        self,
        text: str,
        categories: List[Dict[str, Any]],
        assistant_response: str = "",
        reference_time: str | None = None,
    ) -> Dict:
        """提取记忆意图

        Args:
            text: 用户输入文本
            categories: 用户的 6 个分类列表，每个元素包含 name, description
            assistant_response: AI 回复内容（可选，用于生成回复摘要）
            reference_time: 参考时间戳（可选，用于历史数据导入，格式 "YYYY-MM-DD HH:MM:SS"）。
                            不传则使用系统当前时间。

        Returns:
            Dict: 包含以下字段：
                - summary: 对话的综合摘要
                - importance_score: 对综合摘要的整体重要性评分 (0-3)
                - response_summary: AI 回复的摘要
                - atomic_items: 原子化信息列表，每个元素包含：
                    - category_name: 分类名称
                    - content: 原子化内容
                    - importance_score: 该条信息的评分
        """
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """统计文本的 Token 数量

        Args:
            text: 需要统计的文本

        Returns:
            int: Token 数量
        """
        pass

    async def generate_stream_response(
        self,
        system_prompt: str,
        context: str,
        user_query: str,
    ) -> AsyncGenerator[str, None]:
        """流式返回对话内容（可选实现）

        Args:
            system_prompt: 系统设定
            context: 检索到的记忆上下文
            user_query: 用户当前提问

        Yields:
            str: 文本片段
        """
        # 默认实现：调用非流式方法，一次性返回
        response = await self.generate_chat_response(system_prompt, context, user_query)
        yield response
