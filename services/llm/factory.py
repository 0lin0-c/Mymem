# 🏭 模型工厂：读取 config.py，动态实例化并返回具体的 Provider（OpenAI 或 Claude 等）。
import logging

from core.config import settings
from services.llm.base import BaseLLMProvider
from services.llm.openai_sdk import OpenAIProvider
from services.llm.anthropic_sdk import AnthropicProvider

logger = logging.getLogger(__name__)


class LLMFactory:
    """大模型工厂类

    根据配置动态实例化对应的大模型提供商
    """

    _provider: BaseLLMProvider | None = None

    @classmethod
    def get_provider(cls) -> BaseLLMProvider:
        """获取大模型提供商实例（懒加载单例）

        Returns:
            BaseLLMProvider: 对应的大模型提供商实例

        Raises:
            ValueError: 当配置的 llm_provider 不支持时抛出
        """
        if cls._provider is None:
            provider_name = settings.llm_provider.lower()
            logger.info(f"初始化 LLM Provider: provider={provider_name}")

            # OpenAI 及所有兼容 OpenAI 格式的模型都使用 OpenAIProvider
            # 包括：OpenAI、DeepSeek、阿里通义(Qwen)、智谱(GLM)、MiniMax、自定义 API 等
            if provider_name in ("openai", "openai-compatible", "deepseek", "qwen", "glm", "minimax", "custom"):
                cls._provider = OpenAIProvider()
            elif provider_name == "anthropic":
                cls._provider = AnthropicProvider()
            else:
                logger.error(f"不支持的 LLM Provider: {provider_name}")
                raise ValueError(
                    f"不支持的大模型提供商: {provider_name}。"
                    "支持的提供商: openai, deepseek, qwen, glm, minimax, custom, anthropic"
                )

        return cls._provider

    @classmethod
    def reset(cls):
        """重置provider实例（主要用于测试）"""
        cls._provider = None
        logger.debug("LLM Provider 已重置")
