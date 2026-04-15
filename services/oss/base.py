# ☁️ 对象存储客户端基类
from abc import ABC, abstractmethod


class BaseOSSClient(ABC):
    """对象存储客户端基类

    支持多种后端：
    - 阿里云 OSS
    - 腾讯云 COS
    - AWS S3
    - 本地文件系统（开发测试用）
    """

    @abstractmethod
    async def upload(
        self,
        file_content: bytes,
        filename: str,
        modality: str,
        user_id: str,
    ) -> str:
        """上传文件到存储

        Args:
            file_content: 文件二进制内容
            filename: 原始文件名
            modality: 模态类型 (image/video/voice/document)
            user_id: 用户 ID，用于存储路径隔离

        Returns:
            str: 存储路径或 URL
        """
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """下载文件

        Args:
            path: 存储路径

        Returns:
            bytes: 文件二进制内容
        """
        pass

    @abstractmethod
    async def get_url(self, path: str, expire_seconds: int = 3600) -> str:
        """获取文件的临时访问 URL

        Args:
            path: 存储路径
            expire_seconds: URL 过期时间（秒）

        Returns:
            str: 临时访问 URL
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除文件

        Args:
            path: 存储路径

        Returns:
            bool: 是否删除成功
        """
        pass
