# 🔧 模态处理器模块
from services.memory.handlers.base import BaseHandler
from services.memory.handlers.text_handler import TextHandler
from services.memory.handlers.image_handler import ImageHandler
from services.memory.handlers.video_handler import VideoHandler
from services.memory.handlers.voice_handler import VoiceHandler
from services.memory.handlers.document_handler import DocumentHandler

# 模态类型到 Handler 的映射
HANDLER_MAP = {
    "text": TextHandler,
    "image": ImageHandler,
    "video": VideoHandler,
    "voice": VoiceHandler,
    "document": DocumentHandler,
}


def get_handler(modality: str) -> type[BaseHandler]:
    """根据模态类型获取对应的 Handler 类

    Args:
        modality: 模态类型

    Returns:
        Handler 类

    Raises:
        ValueError: 不支持的模态类型
    """
    handler_class = HANDLER_MAP.get(modality)
    if handler_class is None:
        raise ValueError(f"不支持的模态类型: {modality}，支持的类型: {list(HANDLER_MAP.keys())}")
    return handler_class


__all__ = [
    "BaseHandler",
    "TextHandler",
    "ImageHandler",
    "VideoHandler",
    "VoiceHandler",
    "DocumentHandler",
    "HANDLER_MAP",
    "get_handler",
]
