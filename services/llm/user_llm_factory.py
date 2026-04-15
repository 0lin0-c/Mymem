# 🏭 用户级 LLM 工厂：为每个用户创建独立的 LLM 客户端
import logging
from typing import Optional

from services.llm.base import BaseLLMProvider
from services.llm.openai_sdk import OpenAIProvider
from services.llm.anthropic_sdk import AnthropicProvider

logger = logging.getLogger(__name__)


class UserLLMFactory:
    """用户级 LLM 工厂

    为每个用户维护独立的 LLM 客户端实例。
    与全局 LLMFactory 不同，这里支持用户自定义配置。
    """

    # 用户ID -> LLM 客户端的缓存
    _providers: dict[str, BaseLLMProvider] = {}

    @classmethod
    def get_or_create(
        cls,
        user_id: str,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseLLMProvider:
        """获取或创建用户专属的 LLM 客户端

        Args:
            user_id: 用户ID
            provider: LLM 提供商 (openai/deepseek/qwen/glm/anthropic/custom)
            api_key: API Key
            base_url: API Base URL（可选）
            model: 模型名称（可选）

        Returns:
            BaseLLMProvider: 用户专属的 LLM 客户端
        """
        # 如果已存在且配置相同，直接返回
        if user_id in cls._providers:
            return cls._providers[user_id]

        # 创建新的客户端
        provider_lower = provider.lower()

        if provider_lower in ("openai", "openai-compatible", "deepseek", "qwen", "glm", "minimax", "custom"):
            llm = OpenAIProvider(
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
        elif provider_lower == "anthropic":
            llm = AnthropicProvider(
                api_key=api_key,
                model=model,
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

        cls._providers[user_id] = llm
        logger.info(f"为用户 {user_id} 创建 LLM 客户端: {provider}")

        return llm

    @classmethod
    def get(cls, user_id: str) -> Optional[BaseLLMProvider]:
        """获取用户的 LLM 客户端（不创建）"""
        return cls._providers.get(user_id)

    @classmethod
    def remove(cls, user_id: str) -> None:
        """移除用户的 LLM 客户端缓存"""
        if user_id in cls._providers:
            del cls._providers[user_id]

    @classmethod
    def clear_all(cls) -> None:
        """清空所有缓存"""
        cls._providers.clear()
