# 🎬 视频处理器
import base64
import logging
import struct
import tempfile
import os
from typing import Any, List

from services.memory.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class VideoHandler(BaseHandler):
    """视频模态处理器

    处理视频输入，支持：
    - 关键帧抽取
    - VLM 理解帧内容
    - 生成视频摘要

    支持的输入格式：
    - bytes: 视频二进制数据
    - str: Base64 编码的视频数据
    """

    # 关键帧抽取配置
    MAX_FRAMES = 5  # 最多抽取帧数
    MIN_SCENE_CHANGE = 0.3  # 场景变化阈值

    @property
    def supported_modality(self) -> str:
        return "video"

    async def preprocess(self, content: Any) -> str:
        """预处理视频内容

        1. 抽取关键帧
        2. 使用 VLM 分析每帧
        3. 生成视频摘要

        Args:
            content: 视频数据（bytes 或 Base64 字符串）

        Returns:
            str: 视频的文本描述
        """
        # 转换为 bytes
        if isinstance(content, str):
            video_bytes = base64.b64decode(content)
        elif isinstance(content, bytes):
            video_bytes = content
        else:
            raise ValueError(f"不支持的视频格式: {type(content)}")

        # 抽取关键帧
        frames = await self._extract_key_frames(video_bytes)

        if not frames:
            return "[视频内容无法解析]"

        # 使用 VLM 分析每帧
        frame_descriptions = []
        for i, frame in enumerate(frames):
            description = await self._vlm_describe_frame(frame, i + 1, len(frames))
            frame_descriptions.append(description)

        # 生成视频摘要
        summary = await self._generate_video_summary(frame_descriptions)

        return summary

    async def _extract_key_frames(self, video_bytes: bytes) -> List[bytes]:
        """抽取视频关键帧

        使用 OpenCV 或 ffmpeg 抽取关键帧

        Args:
            video_bytes: 视频二进制数据

        Returns:
            List[bytes]: 关键帧图片列表（JPEG 格式）
        """
        frames = []

        try:
            import cv2
            import numpy as np

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name

            try:
                # 打开视频
                cap = cv2.VideoCapture(tmp_path)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)

                if total_frames == 0 or fps == 0:
                    logger.warning("视频帧数或帧率为 0")
                    return []

                # 计算采样间隔
                interval = max(1, total_frames // self.MAX_FRAMES)

                # 抽取帧
                frame_indices = list(range(0, total_frames, interval))[:self.MAX_FRAMES]

                for idx in frame_indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ret, frame = cap.read()

                    if ret:
                        # 转换为 JPEG
                        _, buffer = cv2.imencode('.jpg', frame)
                        frames.append(buffer.tobytes())

                cap.release()

            finally:
                # 清理临时文件
                os.unlink(tmp_path)

            logger.info(f"抽取 {len(frames)} 个关键帧")

        except ImportError:
            logger.warning("OpenCV 未安装，尝试使用 ffmpeg")

            # 尝试使用 ffmpeg
            frames = await self._extract_frames_ffmpeg(video_bytes)

        except Exception as e:
            logger.error(f"关键帧抽取失败: {e}")

        return frames

    async def _extract_frames_ffmpeg(self, video_bytes: bytes) -> List[bytes]:
        """使用 ffmpeg 抽取关键帧

        Args:
            video_bytes: 视频二进制数据

        Returns:
            List[bytes]: 关键帧图片列表
        """
        frames = []

        try:
            import asyncio

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name

            output_dir = tempfile.mkdtemp()

            try:
                # 使用 ffmpeg 抽帧
                cmd = [
                    "ffmpeg", "-i", tmp_path,
                    "-vf", f"select=not(mod(n\\,{10}))",
                    "-vsync", "vfr",
                    "-frames:v", str(self.MAX_FRAMES),
                    "-f", "image2",
                    f"{output_dir}/frame_%03d.jpg"
                ]

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()

                # 读取生成的帧
                for filename in sorted(os.listdir(output_dir)):
                    if filename.endswith(".jpg"):
                        with open(os.path.join(output_dir, filename), "rb") as f:
                            frames.append(f.read())

            finally:
                # 清理
                os.unlink(tmp_path)
                import shutil
                shutil.rmtree(output_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"ffmpeg 抽帧失败: {e}")

        return frames

    async def _vlm_describe_frame(
        self,
        frame_bytes: bytes,
        frame_num: int,
        total_frames: int,
    ) -> str:
        """使用 VLM 描述帧内容

        Args:
            frame_bytes: 帧图片数据
            frame_num: 帧序号
            total_frames: 总帧数

        Returns:
            str: 帧描述
        """
        frame_base64 = base64.b64encode(frame_bytes).decode("utf-8")

        try:
            from openai import AsyncOpenAI
            from core.config import settings
            import httpx

            http_client = httpx.AsyncClient(trust_env=False)
            if settings.openai_proxy:
                http_client = httpx.AsyncClient(proxy=settings.openai_proxy)

            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or "https://api.openai.com/v1",
                http_client=http_client,
            )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"这是视频的第 {frame_num}/{total_frames} 帧。请简要描述画面内容。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{frame_base64}",
                            },
                        },
                    ],
                }
            ]

            response = await client.chat.completions.create(
                model=settings.vlm_model,
                messages=messages,
                max_tokens=200,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"VLM 帧描述失败: {e}")
            return f"[帧 {frame_num} 描述失败]"

    async def _generate_video_summary(self, frame_descriptions: List[str]) -> str:
        """生成视频摘要

        Args:
            frame_descriptions: 各帧描述列表

        Returns:
            str: 视频摘要
        """
        descriptions_text = "\n".join([
            f"- 帧 {i+1}: {desc}"
            for i, desc in enumerate(frame_descriptions)
        ])

        prompt = f"""基于以下关键帧描述，生成视频内容的综合摘要：

{descriptions_text}

请总结视频的主题、场景变化和关键内容。"""

        try:
            summary = await self.llm.generate_chat_response(
                system_prompt="你是一个视频分析专家，擅长总结视频内容。",
                context="",
                user_query=prompt,
            )
            return summary

        except Exception as e:
            logger.error(f"视频摘要生成失败: {e}")
            # 返回帧描述拼接
            return "视频内容：\n" + descriptions_text

    async def get_vector(self, text: str) -> bytes:
        """生成向量"""
        embedding = await self.llm.get_embedding(text)
        return struct.pack(f'{len(embedding)}f', *embedding)

    async def store_raw_content(self, content: Any) -> str:
        """存储视频到 OSS

        Args:
            content: 视频数据（bytes）

        Returns:
            str: OSS 存储路径
        """
        if not self.oss_client:
            raise ValueError("OSS 客户端未配置")

        if not self.user_id:
            raise ValueError("user_id 未设置")

        if isinstance(content, str):
            video_bytes = base64.b64decode(content)
        elif isinstance(content, bytes):
            video_bytes = content
        else:
            raise ValueError(f"不支持的视频格式: {type(content)}")

        # 生成文件名
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"video_{timestamp}_{unique_id}.mp4"

        # 上传到 OSS
        path = await self.oss_client.upload(video_bytes, filename, "video", self.user_id)
        logger.info(f"视频存储成功: {path}")

        return path
