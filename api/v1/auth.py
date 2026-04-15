# 🔐 认证路由：处理用户登录
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.auth_schema import LoginRequest, AuthResponse
from repositories import UserRepository
from services.session import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["认证"])


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """用户登录

    验证用户名和密码，返回用户信息。
    """
    logger.info(f"登录请求: username={request.username}")
    user_repo = UserRepository(session)

    # 查找用户
    user = await user_repo.get_by_username(request.username)
    if not user:
        logger.warning(f"登录失败: 用户不存在, username={request.username}")
        return AuthResponse(
            success=False,
            message="用户不存在",
        )

    # 验证密码（简单比对，生产环境应使用 bcrypt）
    if user.password != request.password:
        logger.warning(f"登录失败: 密码错误, username={request.username}")
        return AuthResponse(
            success=False,
            message="密码错误",
        )

    logger.info(f"登录成功: username={request.username}, user_id={user.id}")

    # 从 agent_persona_template 提取 AI 名字
    ai_name = None
    if user.agent_persona_template:
        # 尝试从模板中提取 AI 名字
        import re
        match = re.search(r"你是([^，。]+)，", user.agent_persona_template)
        if match:
            ai_name = match.group(1)

    return AuthResponse(
        success=True,
        user_id=user.id,
        username=user.username,
        ai_name=ai_name,
        llm_configured=bool(user.llm_provider and user.llm_api_key),
        message="登录成功",
    )


@router.post("/logout")
async def logout(
    user_id: str,
    session_id: str | None = None,
):
    """用户登出

    清除服务端的会话状态。

    Args:
        user_id: 用户ID
        session_id: 会话ID（可选，如果提供则销毁该会话）
    """
    # 销毁会话
    if session_id:
        session_manager.destroy_session(session_id)
        logger.info(f"会话 {session_id} 已销毁")

    # 清除用户级 LLM 客户端缓存
    from services.llm.user_llm_factory import UserLLMFactory
    UserLLMFactory.remove(user_id)
    logger.info(f"用户 {user_id} 的 LLM 客户端缓存已清除")

    return {"success": True, "message": "登出成功"}
