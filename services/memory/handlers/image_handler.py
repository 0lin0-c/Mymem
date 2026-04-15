# 🖼️ 图片处理器
import base64
import logging
import struct
from typing import Any

from services.memory.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class ImageHandler(BaseHandler):
    """图片模态处理器

    处理图片输入，支持：
    - 上传到 OSS
    - VLM 理解图片内容（OpenAI GPT-4V / GPT-4o）
    - 可选 OCR 提取文字

    支持的输入格式：
    - bytes: 图片二进制数据
    - str: Base64 编码的图片数据
    """

    @property
    def supported_modality(self) -> str:
        return "image"

    async def preprocess(self, content: Any) -> str:
        """预处理图片内容

        使用 VLM 生成图片描述

        Args:
            content: 图片数据（bytes 或 Base64 字符串）

        Returns:
            str: 图片的文本描述
        """
        # 转换为 Base64
        if isinstance(content, bytes):
            image_base64 = base64.b64encode(content).decode("utf-8")
        elif isinstance(content, str):
            # 如果已经是 Base64，直接使用
            image_base64 = content
        else:
            raise ValueError(f"不支持的图片格式: {type(content)}")

        # 使用 VLM 生成图片描述
        description = await self._vlm_describe(image_base64)

        return description

    async def _vlm_describe(self, image_base64: str) -> str:
        """使用 VLM 生成图片描述

        支持 OpenAI GPT-4V / GPT-4o 或兼容的 VLM 服务

        Args:
            image_base64: Base64 编码的图片

        Returns:
            str: 图片描述
        """
        try:
            # 检测图片格式
            image_format = self._detect_image_format(image_base64)

            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请详细描述这张图片的内容。包括：\n1. 主要对象和场景\n2. 颜色和构图\n3. 如果有文字，请提取出来\n4. 图片传达的情感或主题",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_base64}",
                            },
                        },
                    ],
                }
            ]

            # 调用 VLM
            from core.config import settings
            from openai import AsyncOpenAI
            import httpx

            http_client = httpx.AsyncClient(trust_env=False)
            if settings.openai_proxy:
                http_client = httpx.AsyncClient(proxy=settings.openai_proxy)

            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or "https://api.openai.com/v1",
                http_client=http_client,
            )

            response = await client.chat.completions.create(
                model=settings.vlm_model,
                messages=messages,
                max_tokens=1000,
            )

            description = response.choices[0].message.content
            logger.info(f"VLM 图片描述生成成功: {len(description)} 字符")

            return description

        except Exception as e:
            logger.error(f"VLM 图片描述生成失败: {e}")
            # 返回默认描述
            return "[图片内容无法解析]"

    def _detect_image_format(self, base64_data: str) -> str:
        """检测图片格式

        通过 Base64 数据头部判断图片格式
        """
        # 解码前几个字节
        try:
            header = base64.b64decode(base64_data[:32])

            # PNG: 89 50 4E 47
            if header[:4] == b'\x89PNG':
                return "png"
            # JPEG: FF D8 FF
            elif header[:3] == b'\xff\xd8\xff':
                return "jpeg"
            # GIF: 47 49 46 38
            elif header[:4] == b'GIF8':
                return "gif"
            # WebP: 52 49 46 46 ... 57 45 42 50
            elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                return "webp"
            else:
                return "jpeg"  # 默认 JPEG
        except Exception:
            return "jpeg"

    async def get_vector(self, text: str) -> bytes:
        """生成向量"""
        embedding = await self.llm.get_embedding(text)
        return struct.pack(f'{len(embedding)}f', *embedding)

    async def store_raw_content(self, content: Any) -> str:
        """存储图片到 OSS

        Args:
            content: 图片数据（bytes）

        Returns:
            str: OSS 存储路径
        """
        if not self.oss_client:
            raise ValueError("OSS 客户端未配置")

        if not self.user_id:
            raise ValueError("user_id 未设置")

        if isinstance(content, str):
            # Base64 解码
            content = base64.b64decode(content)

        if not isinstance(content, bytes):
            raise ValueError(f"不支持的图片格式: {type(content)}")

        # 生成文件名
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"image_{timestamp}_{unique_id}.jpg"

        # 上传到 OSS
        path = await self.oss_client.upload(content, filename, "image", self.user_id)
        logger.info(f"图片存储成功: {path}")

        return path
