# 📝 文本处理器
import struct
from typing import Any

from services.memory.handlers.base import BaseHandler


class TextHandler(BaseHandler):
    """文本模态处理器

    处理纯文本对话，是最基础的处理器。
    """

    @property
    def supported_modality(self) -> str:
        return "text"

    async def preprocess(self, content: Any) -> str:
        """文本无需预处理，直接返回"""
        if not isinstance(content, str):
            raise ValueError(f"TextHandler 期望 str 类型，收到: {type(content)}")
        return content

    async def get_vector(self, text: str) -> bytes:
        """调用 LLM 生成向量"""
        embedding = await self.llm.get_embedding(text)
        return struct.pack(f'{len(embedding)}f', *embedding)

    async def store_raw_content(self, content: Any) -> str:
        """文本直接返回原文，无需存储到 OSS"""
        if not isinstance(content, str):
            raise ValueError(f"TextHandler 期望 str 类型，收到: {type(content)}")
        return content
