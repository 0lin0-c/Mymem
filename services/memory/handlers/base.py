# 📐 模态处理器基类
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.llm.base import BaseLLMProvider
from services.oss.base import BaseOSSClient


class BaseHandler(ABC):
    """模态处理器抽象基类

    所有模态处理器必须实现以下方法：
    1. supported_modality - 返回支持的模态类型
    2. preprocess - 预处理原始内容为文本描述
    3. get_vector - 生成向量
    4. store_raw_content - 存储原始内容

    不同模态的预处理逻辑不同：
    - text: 直接使用
    - image: 调用 VLM/OCR 提取描述
    - video: 帧抽取 + 场景识别
    - voice: ASR 转文字
    - document: OCR/文档解析
    """

    def __init__(
        self,
        session: AsyncSession,
        llm: BaseLLMProvider,
        oss_client: BaseOSSClient | None = None,
        user_id: str | None = None,
    ):
        self.session = session
        self.llm = llm
        self.oss_client = oss_client
        self.user_id = user_id

    @property
    @abstractmethod
    def supported_modality(self) -> str:
        """返回支持的模态类型

        Returns:
            str: text/image/video/voice/document
        """
        pass

    @abstractmethod
    async def preprocess(self, content: Any) -> str:
        """预处理：将原始内容转为文本描述

        不同模态的实现：
        - text: 直接返回原文
        - image: 调用 VLM 生成图片描述
        - video: 抽取关键帧 + VLM 描述
        - voice: ASR 语音转文字
        - document: OCR + 文档解析

        Args:
            content: 原始内容（文本/文件字节/URL等）

        Returns:
            str: 预处理后的文本描述
        """
        pass

    @abstractmethod
    async def get_vector(self, text: str) -> bytes:
        """将文本转为向量

        Args:
            text: 需要向量化的文本

        Returns:
            bytes: 向量的二进制表示（float32 格式）
        """
        pass

    @abstractmethod
    async def store_raw_content(self, content: Any) -> str:
        """存储原始内容

        对于文本：直接返回原文
        对于文件：上传到 OSS 并返回路径

        Args:
            content: 原始内容

        Returns:
            str: 存储路径或原文
        """
        pass
