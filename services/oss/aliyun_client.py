# ☁️ 阿里云 OSS 存储实现
import logging
import uuid
from datetime import datetime
from typing import Optional

from services.oss.base import BaseOSSClient
from core.config import settings

logger = logging.getLogger(__name__)


class AliyunOSSClient(BaseOSSClient):
    """阿里云 OSS 对象存储客户端

    用于生产环境，支持：
    - 文件上传/下载
    - 临时签名 URL
    - 按模态分目录存储
    """

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        endpoint: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        """初始化阿里云 OSS 客户端

        Args:
            access_key_id: 阿里云 AccessKey ID
            access_key_secret: 阿里云 AccessKey Secret
            endpoint: OSS 端点，如 oss-cn-hangzhou.aliyuncs.com
            bucket_name: 存储桶名称
        """
        self.access_key_id = access_key_id or settings.aliyun_oss_access_key_id
        self.access_key_secret = access_key_secret or settings.aliyun_oss_access_key_secret
        self.endpoint = endpoint or settings.aliyun_oss_endpoint
        self.bucket_name = bucket_name or settings.aliyun_oss_bucket_name

        # 延迟初始化 OSS 客户端
        self._bucket = None

        # 验证配置
        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            raise ValueError(
                "阿里云 OSS 配置不完整，请设置 ALIYUN_OSS_ACCESS_KEY_ID, "
                "ALIYUN_OSS_ACCESS_KEY_SECRET, ALIYUN_OSS_ENDPOINT, ALIYUN_OSS_BUCKET_NAME"
            )

    @property
    def bucket(self):
        """延迟初始化 OSS Bucket 对象"""
        if self._bucket is None:
            try:
                import oss2
                auth = oss2.Auth(self.access_key_id, self.access_key_secret)
                self._bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            except ImportError:
                raise ImportError(
                    "请安装 oss2 库: pip install oss2"
                )
        return self._bucket

    def _generate_key(self, filename: str, modality: str, user_id: str) -> str:
        """生成 OSS 存储键

        格式: {user_id}/{modality}/{YYYY-MM-DD}/{uuid}.{ext}
        """
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        date_str = datetime.now().strftime("%Y-%m-%d")
        unique_id = uuid.uuid4().hex[:8]

        return f"{user_id}/{modality}/{date_str}/{unique_id}.{ext}"

    async def upload(
        self,
        file_content: bytes,
        filename: str,
        modality: str,
        user_id: str,
    ) -> str:
        """上传文件到 OSS

        Args:
            file_content: 文件二进制内容
            filename: 原始文件名
            modality: 模态类型 (image/video/voice/document)
            user_id: 用户 ID，用于存储路径隔离

        Returns:
            str: OSS 存储键
        """
        key = self._generate_key(filename, modality, user_id)

        try:
            # OSS SDK 是同步的，需要在线程池中执行
            import asyncio
            loop = asyncio.get_running_loop()

            await loop.run_in_executor(
                None,
                self.bucket.put_object,
                key,
                file_content,
            )

            logger.info(f"文件上传成功: {key}")
            return key

        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            raise

    async def download(self, path: str) -> bytes:
        """从 OSS 下载文件

        Args:
            path: OSS 存储键

        Returns:
            bytes: 文件二进制内容
        """
        try:
            import asyncio
            loop = asyncio.get_running_loop()

            result = await loop.run_in_executor(
                None,
                self.bucket.get_object,
                path,
            )

            return result.read()

        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            raise

    async def get_url(self, path: str, expire_seconds: int = 3600) -> str:
        """获取文件的临时签名 URL

        Args:
            path: OSS 存储键
            expire_seconds: URL 过期时间（秒）

        Returns:
            str: 签名 URL
        """
        try:
            import asyncio
            loop = asyncio.get_running_loop()

            url = await loop.run_in_executor(
                None,
                self.bucket.sign_url,
                "GET",
                path,
                expire_seconds,
            )

            return url

        except Exception as e:
            logger.error(f"获取签名 URL 失败: {e}")
            raise

    async def delete(self, path: str) -> bool:
        """删除 OSS 文件

        Args:
            path: OSS 存储键

        Returns:
            bool: 是否删除成功
        """
        try:
            import asyncio
            loop = asyncio.get_running_loop()

            await loop.run_in_executor(
                None,
                self.bucket.delete_object,
                path,
            )

            logger.info(f"文件删除成功: {path}")
            return True

        except Exception as e:
            logger.error(f"文件删除失败: {e}")
            return False

    async def exists(self, path: str) -> bool:
        """检查文件是否存在

        Args:
            path: OSS 存储键

        Returns:
            bool: 文件是否存在
        """
        try:
            import asyncio
            loop = asyncio.get_running_loop()

            result = await loop.run_in_executor(
                None,
                self.bucket.object_exists,
                path,
            )

            return result

        except Exception as e:
            logger.error(f"检查文件存在失败: {e}")
            return False
