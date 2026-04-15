# 📦 对象存储服务
from services.oss.base import BaseOSSClient
from services.oss.local_client import LocalOSSClient
from services.oss.aliyun_client import AliyunOSSClient

__all__ = [
    "BaseOSSClient",
    "LocalOSSClient",
    "AliyunOSSClient",
]


def get_oss_client() -> BaseOSSClient:
    """根据配置获取 OSS 客户端实例

    Returns:
        BaseOSSClient: OSS 客户端实例
    """
    from core.config import settings

    provider = settings.oss_provider.lower()

    if provider == "aliyun":
        return AliyunOSSClient()
    else:
        return LocalOSSClient()
