# 🤖 Claude 适配器：封装 Anthropic 官方库
import json
import logging
from typing import AsyncGenerator, Dict, List

import anthropic

from core.config import settings
from services.llm.base import BaseLLMProvider
from services.llm.tools import (
    build_chat_prompt,
    build_memory_extraction_prompt,
    EXTRACT_MEMORY_TOOL_ANTHROPIC,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude 大模型提供商"""

    def __init__(self):
        client_kwargs = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            client_kwargs["base_url"] = settings.anthropic_base_url
        self.client = anthropic.AsyncAnthropic(**client_kwargs)
        self.embedding_dimensions = settings.embedding_dimensions

    async def generate_chat_response(
        self,
        system_prompt: str,
        context: str,
        user_query: str,
    ) -> str:
        """生成对话回复"""
        prompts = build_chat_prompt(context, user_query)
        logger.debug(f"调用 Anthropic Chat API: model=claude-3-5-sonnet-20241022")

        message = await self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=system_prompt or prompts["system_prompt"],
            messages=[
                {
                    "role": "user",
                    "content": prompts["user_prompt"],
                }
            ],
        )

        logger.debug(f"Anthropic Chat API 调用成功: response_length={len(message.content[0].text)}")
        return message.content[0].text

    async def get_embedding(self, text: str) -> List[float]:
        """文本转向量"""
        raise NotImplementedError(
            "Anthropic 官方不提供 embedding API。"
            "请在 .env 中设置 LLM_PROVIDER=openai 来使用 embedding 功能。"
        )

    async def extract_memory_intent(
        self,
        text: str,
        categories: List[Dict],
        assistant_response: str = "",
        reference_time: str | None = None,
    ) -> Dict:
        """提取记忆意图"""
        logger.debug(f"调用 Anthropic 记忆提取: text_length={len(text)}, categories_count={len(categories)}")
        system_prompt = build_memory_extraction_prompt(categories, reference_time=reference_time)

        user_content = f"[User Input]\n{text}"
        if assistant_response:
            user_content += f"\n\n[AI Response]\n{assistant_response}"

        try:
            message = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_content}
                ],
                tools=[EXTRACT_MEMORY_TOOL_ANTHROPIC],
                tool_choice={"type": "tool", "name": "extract_memory"},
            )

            for block in message.content:
                if block.type == "tool_use":
                    result = block.input
                    return {
                        "summary": result.get("summary", ""),
                        "importance_score": result.get("importance_score", 2),
                        "response_summary": result.get("response_summary", ""),
                        "atomic_items": result.get("atomic_items", []),
                    }

        except Exception as e:
            logger.error(f"extract_memory_intent 失败: {type(e).__name__}: {e}")

        logger.warning("extract_memory_intent 失败，返回默认值")
        return {
            "summary": text[:200],
            "importance_score": 2,
            "response_summary": assistant_response[:50] if assistant_response else "",
            "atomic_items": [],
        }

    async def count_tokens(self, text: str) -> int:
        """统计文本的 Token 数量

        使用 Anthropic 官方 Token 计数 API

        Args:
            text: 需要统计的文本

        Returns:
            int: Token 数量
        """
        try:
            result = await self.client.messages.count_tokens(
                model="claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": text}],
            )
            return result.input_tokens
        except Exception as e:
            logger.error(f"Token 计数失败: {type(e).__name__}: {e}")
            # 回退到估算值：平均每 4 字符约 1 token
            return len(text) // 4

    async def generate_stream_response(
        self,
        system_prompt: str,
        context: str,
        user_query: str,
    ) -> AsyncGenerator[str, None]:
        """流式返回对话内容

        Args:
            system_prompt: 系统设定
            context: 检索到的记忆上下文
            user_query: 用户当前提问

        Yields:
            str: 文本片段
        """
        logger.debug(f"调用 Anthropic 流式 Chat API: model=claude-3-5-sonnet-20241022")
        prompts = build_chat_prompt(context, user_query)

        try:
            async with self.client.messages.stream(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                system=system_prompt or prompts["system_prompt"],
                messages=[
                    {"role": "user", "content": prompts["user_prompt"]},
                ],
            ) as stream:
                async for text in stream.text_stream:
                    yield text

            logger.debug("Anthropic 流式 Chat API 完成")

        except Exception as e:
            logger.error(f"流式输出失败: {type(e).__name__}: {e}")
            raise
