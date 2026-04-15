# 🚪 接口路由层：对前端/客户端暴露的 HTTP RESTful 接口。
# 💉 依赖注入：提供贯穿全局的依赖函数，比如从请求头解析 JWT Token 获取当前操作的 `user_id`。
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.llm.base import BaseLLMProvider
from services.llm.factory import LLMFactory


def get_llm_service() -> BaseLLMProvider:
    """获取大模型服务的依赖函数

    使用方式：
        @router.post("/chat")
        async def chat(llm: BaseLLMProvider = Depends(get_llm_service)):
            ...

    Returns:
        BaseLLMProvider: 当前配置的大模型提供商实例
    """
    return LLMFactory.get_provider()
