# 🔌 OpenAI 适配器：封装官方 openai 库
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List

import httpx
import tiktoken
from openai import AsyncOpenAI

from core.config import settings
from services.llm.base import BaseLLMProvider
from services.llm.tools import (
    build_chat_prompt,
    build_memory_extraction_prompt,
    EXTRACT_MEMORY_TOOL_OPENAI,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [0.5, 1.0, 2.0]


def _create_http_client() -> httpx.AsyncClient:
    """创建 httpx 客户端"""
    # 设置合理的超时时间：连接 30s，读取 120s，写入 30s
    timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)

    if settings.openai_proxy:
        return httpx.AsyncClient(proxy=settings.openai_proxy, timeout=timeout)
    else:
        return httpx.AsyncClient(trust_env=False, timeout=timeout)


def _is_unsupported_tool_choice_error(error: Exception) -> bool:
    message = str(error).lower()
    return "tool_choice" in message and "not support" in message


def _normalize_memory_result(result: Dict, text: str, assistant_response: str) -> Dict:
    atomic_items = result.get("atomic_items", [])
    if not isinstance(atomic_items, list):
        atomic_items = []
    for item in atomic_items:
        if not isinstance(item, dict):
            continue
        category_name = item.get("category_name")
        if isinstance(category_name, str):
            item["category_name"] = category_name.strip().strip("[]")

    return {
        "summary": result.get("summary", "") or text[:200],
        "importance_score": result.get("importance_score", 2),
        "response_summary": result.get("response_summary", "")
        or (assistant_response[:50] if assistant_response else ""),
        "atomic_items": atomic_items,
    }


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 大模型提供商"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        """
        Args:
            api_key: API Key（可选，默认使用全局配置）
            base_url: API Base URL（可选，默认使用全局配置）
            model: 模型名称（可选，默认使用全局配置）
        """
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url or "https://api.openai.com/v1",
            http_client=_create_http_client(),
        )

        self.chat_model = model or settings.chat_model
        self.embedding_model = settings.embedding_model
        self.embedding_dimensions = settings.embedding_dimensions

        embedding_api_key = settings.embedding_api_key or settings.openai_api_key
        embedding_base_url = settings.embedding_base_url or settings.openai_base_url or "https://api.openai.com/v1"

        if embedding_base_url and not embedding_base_url.startswith("http"):
            logger.warning("EMBEDDING_BASE_URL 配置无效，将使用 OPENAI_BASE_URL")
            embedding_base_url = settings.openai_base_url or "https://api.openai.com/v1"

        self.embedding_client = AsyncOpenAI(
            api_key=embedding_api_key,
            base_url=embedding_base_url,
            http_client=_create_http_client(),
        )

        # Token 计数器
        self._tokenizer = tiktoken.get_encoding("cl100k_base")
        self._supports_forced_tool_choice = True

    async def generate_chat_response(
        self,
        system_prompt: str,
        context: str,
        user_query: str,
    ) -> str:
        """生成对话回复"""
        prompts = build_chat_prompt(context, user_query)

        messages = [
            {"role": "system", "content": system_prompt or prompts["system_prompt"]},
            {"role": "user", "content": prompts["user_prompt"]},
        ]

        logger.debug(f"调用 Chat API: model={self.chat_model}, messages_count={len(messages)}")
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.chat_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000,
                )
                logger.debug(f"Chat API 调用成功: response_length={len(response.choices[0].message.content)}")
                return response.choices[0].message.content
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                logger.warning(f"API 返回空响应，重试 {MAX_RETRIES} 次后仍失败: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"API 调用失败: {type(e).__name__}: {e}")
                break

        raise last_error or Exception("API 调用失败")

    async def get_embedding(self, text: str) -> List[float]:
        """文本转向量"""
        try:
            logger.debug(f"调用 Embedding API: model={self.embedding_model}, text_length={len(text)}")
            response = await self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=self.embedding_dimensions,
            )
            logger.debug(f"Embedding API 调用成功: dimensions={len(response.data[0].embedding)}")
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding API 调用失败: {type(e).__name__}: {e}")
            raise

    async def extract_memory_intent(
        self,
        text: str,
        categories: List[Dict],
        assistant_response: str = "",
        reference_time: str | None = None,
        target_category_name: str | None = None,
    ) -> Dict:
        """提取记忆意图

        使用 Function Calling 引导模型输出结构化 JSON

        Args:
            text: 用户输入文本
            categories: 用户的 6 个分类列表
            assistant_response: AI 回复内容
            reference_time: 参考时间戳（可选，用于历史数据导入）
        """
        logger.debug(
            "调用记忆提取: text_length=%s, categories_count=%s, target_category=%s",
            len(text),
            len(categories),
            target_category_name,
        )
        tools = [EXTRACT_MEMORY_TOOL_OPENAI]
        system_prompt = build_memory_extraction_prompt(
            categories,
            reference_time=reference_time,
            target_category_name=target_category_name,
        )

        # 构建用户消息
        user_content = f"[User Input]\n{text}"
        if assistant_response:
            user_content += f"\n\n[AI Response]\n{assistant_response}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                request_kwargs = {
                    "model": self.chat_model,
                    "messages": messages,
                    "tools": tools,
                }
                if self._supports_forced_tool_choice:
                    request_kwargs["tool_choice"] = {
                        "type": "function",
                        "function": {"name": "extract_memory"},
                    }

                response = await self.client.chat.completions.create(**request_kwargs)

                if not response.choices:
                    raise ValueError("API 返回空 choices")

                message = response.choices[0].message
                if not message.tool_calls:
                    if not self._supports_forced_tool_choice:
                        return await self._extract_memory_intent_json_response(
                            system_prompt,
                            user_content,
                            text,
                            assistant_response,
                        )
                    raise ValueError("API 返回空 tool_calls")

                tool_call = message.tool_calls[0]
                result = json.loads(tool_call.function.arguments)

                return _normalize_memory_result(result, text, assistant_response)
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                logger.warning(f"extract_memory_intent 重试 {MAX_RETRIES} 次后仍失败: {e}")
            except Exception as e:
                last_error = e
                if (
                    self._supports_forced_tool_choice
                    and _is_unsupported_tool_choice_error(e)
                ):
                    self._supports_forced_tool_choice = False
                    logger.warning(
                        "model=%s does not support forced tool_choice; retrying with tools auto mode",
                        self.chat_model,
                    )
                    continue
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                logger.error(f"extract_memory_intent 失败: {type(e).__name__}: {e}")

        # 失败时返回默认值
        logger.warning(f"extract_memory_intent 失败，返回默认值: error={last_error}")
        return {
            "summary": text[:200],
            "importance_score": 2,
            "response_summary": assistant_response[:50] if assistant_response else "",
            "atomic_items": [],
        }

    async def _extract_memory_intent_json_response(
        self,
        system_prompt: str,
        user_content: str,
        text: str,
        assistant_response: str,
    ) -> Dict:
        json_system_prompt = (
            f"{system_prompt}\n\n"
            "Return only valid JSON with keys: summary, importance_score, "
            "response_summary, atomic_items. Do not use markdown."
        )
        response = await self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": json_system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        if not response.choices:
            raise ValueError("API 杩斿洖绌?choices")

        content = response.choices[0].message.content or ""
        result = json.loads(content)
        return _normalize_memory_result(result, text, assistant_response)

    async def count_tokens(self, text: str) -> int:
        """统计文本的 Token 数量

        使用 tiktoken 库，按 cl100k_base 编码计算（适用于 GPT-4, GPT-3.5-turbo 等）

        Args:
            text: 需要统计的文本

        Returns:
            int: Token 数量
        """
        return len(self._tokenizer.encode(text))

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
        logger.debug(f"调用流式 Chat API: model={self.chat_model}")
        prompts = build_chat_prompt(context, user_query)

        messages = [
            {"role": "system", "content": system_prompt or prompts["system_prompt"]},
            {"role": "user", "content": prompts["user_prompt"]},
        ]

        try:
            stream = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

            logger.debug("流式 Chat API 完成")

        except Exception as e:
            logger.error(f"流式输出失败: {type(e).__name__}: {e}")
            raise
