# 💾 本地文件存储实现（开发测试用）
import logging
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from services.oss.base import BaseOSSClient
from core.config import settings

logger = logging.getLogger(__name__)


class LocalOSSClient(BaseOSSClient):
    """本地文件系统存储

    用于开发和测试环境，文件存储在本地目录。
    生产环境应替换为阿里云 OSS 或其他云存储。
    """

    def __init__(self, base_path: Optional[str] = None):
        """初始化本地存储

        Args:
            base_path: 存储根目录，默认为项目下的 storage/ 目录
        """
        self.base_path = Path(base_path or os.path.join(os.getcwd(), "storage"))
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 按模态创建子目录
        for modality in ["image", "video", "voice", "document"]:
            (self.base_path / modality).mkdir(exist_ok=True)

    def _generate_path(self, filename: str, modality: str, user_id: str) -> str:
        """生成存储路径

        格式: {user_id}/{modality}/{YYYY-MM-DD}/{uuid}.{ext}
        """
        ext = Path(filename).suffix or ".bin"
        date_str = datetime.now().strftime("%Y-%m-%d")
        unique_id = uuid.uuid4().hex[:8]
        new_filename = f"{unique_id}{ext}"

        return f"{user_id}/{modality}/{date_str}/{new_filename}"

    async def upload(
        self,
        file_content: bytes,
        filename: str,
        modality: str,
        user_id: str,
    ) -> str:
        """上传文件到本地目录"""
        if not user_id:
            raise ValueError("user_id 不能为空")

        relative_path = self._generate_path(filename, modality, user_id)
        full_path = self.base_path / relative_path

        # 确保目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(full_path, "wb") as f:
            f.write(file_content)

        logger.debug(f"文件上传成功: path={relative_path}, size={len(file_content)} bytes")
        return relative_path

    async def download(self, path: str) -> bytes:
        """从本地读取文件"""
        full_path = self.base_path / path

        if not full_path.exists():
            logger.warning(f"文件下载失败: 文件不存在, path={path}")
            raise FileNotFoundError(f"文件不存在: {path}")

        with open(full_path, "rb") as f:
            content = f.read()

        logger.debug(f"文件下载成功: path={path}, size={len(content)} bytes")
        return content

    async def get_url(self, path: str, expire_seconds: int = 3600) -> str:
        """获取本地文件路径（开发环境直接返回绝对路径）

        生产环境应返回带签名的临时 URL
        """
        full_path = self.base_path / path

        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        # 开发环境返回绝对路径
        # 生产环境应返回 HTTP URL
        return str(full_path.absolute())

    async def delete(self, path: str) -> bool:
        """删除本地文件"""
        full_path = self.base_path / path

        if full_path.exists():
            full_path.unlink()
            logger.debug(f"文件删除成功: path={path}")
            return True

        logger.debug(f"文件删除跳过: 文件不存在, path={path}")
        return False
