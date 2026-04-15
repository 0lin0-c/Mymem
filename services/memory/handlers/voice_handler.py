# 🎤 语音处理器
import base64
import logging
import struct
from typing import Any

from services.memory.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class VoiceHandler(BaseHandler):
    """语音模态处理器

    处理语音输入，支持：
    - 上传到 OSS
    - ASR 语音转文字（OpenAI Whisper 或阿里云 ASR）

    支持的输入格式：
    - bytes: 音频二进制数据
    - str: Base64 编码的音频数据
    """

    @property
    def supported_modality(self) -> str:
        return "voice"

    async def preprocess(self, content: Any) -> str:
        """预处理语音内容

        使用 ASR 转录为文字

        Args:
            content: 音频数据（bytes 或 Base64 字符串）

        Returns:
            str: 转录的文本
        """
        # 转换为 bytes
        if isinstance(content, str):
            audio_bytes = base64.b64decode(content)
        elif isinstance(content, bytes):
            audio_bytes = content
        else:
            raise ValueError(f"不支持的音频格式: {type(content)}")

        # 使用 ASR 转录
        transcript = await self._asr_transcribe(audio_bytes)

        return transcript

    async def _asr_transcribe(self, audio_bytes: bytes) -> str:
        """使用 ASR 转录音频

        根据配置选择 ASR 提供商：
        - OpenAI Whisper
        - 阿里云 ASR

        Args:
            audio_bytes: 音频二进制数据

        Returns:
            str: 转录文本
        """
        from core.config import settings

        provider = settings.asr_provider.lower()

        if provider == "openai":
            return await self._openai_whisper_transcribe(audio_bytes)
        elif provider == "aliyun":
            return await self._aliyun_asr_transcribe(audio_bytes)
        else:
            logger.warning(f"未知的 ASR 提供商: {provider}，使用 OpenAI Whisper")
            return await self._openai_whisper_transcribe(audio_bytes)

    async def _openai_whisper_transcribe(self, audio_bytes: bytes) -> str:
        """使用 OpenAI Whisper 转录

        Args:
            audio_bytes: 音频二进制数据

        Returns:
            str: 转录文本
        """
        try:
            from openai import AsyncOpenAI
            from core.config import settings
            import httpx
            import io

            http_client = httpx.AsyncClient(trust_env=False)
            if settings.openai_proxy:
                http_client = httpx.AsyncClient(proxy=settings.openai_proxy)

            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or "https://api.openai.com/v1",
                http_client=http_client,
            )

            # 创建临时文件对象
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.mp3"  # Whisper 需要文件名来判断格式

            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="zh",  # 中文
            )

            transcript = response.text
            logger.info(f"Whisper 转录成功: {len(transcript)} 字符")

            return transcript

        except Exception as e:
            logger.error(f"Whisper 转录失败: {e}")
            return "[语音转文字失败]"

    async def _aliyun_asr_transcribe(self, audio_bytes: bytes) -> str:
        """使用阿里云 ASR 转录

        Args:
            audio_bytes: 音频二进制数据

        Returns:
            str: 转录文本
        """
        try:
            from core.config import settings
            import hashlib
            import hmac
            import base64
            import time
            import urllib.parse
            import aiohttp

            # 阿里云 ASR API 参数
            app_key = settings.aliyun_asr_app_key
            access_key_id = settings.aliyun_asr_access_key_id or settings.aliyun_oss_access_key_id
            access_key_secret = settings.aliyun_asr_access_key_secret or settings.aliyun_oss_access_key_secret

            if not all([app_key, access_key_id, access_key_secret]):
                raise ValueError("阿里云 ASR 配置不完整")

            # 上传音频文件获取 URL（简化实现，实际需要先上传到 OSS）
            # 这里假设音频已经上传，或者使用实时语音识别 API

            # 使用阿里云一句话识别 API
            url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/asr"

            params = {
                "appkey": app_key,
                "format": "pcm",
                "sample_rate": 16000,
                "enable_punctuation_prediction": True,
                "enable_inverse_text_normalization": True,
            }

            # 签名
            timestamp = str(int(time.time()))
            signature_nonce = str(int(time.time() * 1000))

            headers = {
                "Content-Type": "application/octet-stream",
                "X-NLS-Token": self._generate_token(access_key_id, access_key_secret),
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    params=params,
                    data=audio_bytes,
                    headers=headers,
                ) as response:
                    result = await response.json()

                    if result.get("status") == 20000000:
                        transcript = result.get("result", "")
                        logger.info(f"阿里云 ASR 转录成功: {len(transcript)} 字符")
                        return transcript
                    else:
                        raise Exception(f"ASR 错误: {result}")

        except Exception as e:
            logger.error(f"阿里云 ASR 转录失败: {e}")
            return "[语音转文字失败]"

    def _generate_token(self, access_key_id: str, access_key_secret: str) -> str:
        """生成阿里云 API Token"""
        import time
        import hashlib
        import base64
        import hmac

        timestamp = str(int(time.time()))
        signature_nonce = str(int(time.time() * 1000))

        string_to_sign = f"{access_key_id}{timestamp}{signature_nonce}"
        signature = hmac.new(
            access_key_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        token = base64.b64encode(signature).decode("utf-8")
        return token

    async def get_vector(self, text: str) -> bytes:
        """生成向量"""
        embedding = await self.llm.get_embedding(text)
        return struct.pack(f'{len(embedding)}f', *embedding)

    async def store_raw_content(self, content: Any) -> str:
        """存储语音到 OSS

        Args:
            content: 音频数据（bytes）

        Returns:
            str: OSS 存储路径
        """
        if not self.oss_client:
            raise ValueError("OSS 客户端未配置")

        if not self.user_id:
            raise ValueError("user_id 未设置")

        if isinstance(content, str):
            audio_bytes = base64.b64decode(content)
        elif isinstance(content, bytes):
            audio_bytes = content
        else:
            raise ValueError(f"不支持的音频格式: {type(content)}")

        # 生成文件名
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"voice_{timestamp}_{unique_id}.mp3"

        # 上传到 OSS
        path = await self.oss_client.upload(audio_bytes, filename, "voice", self.user_id)
        logger.info(f"语音存储成功: {path}")

        return path
