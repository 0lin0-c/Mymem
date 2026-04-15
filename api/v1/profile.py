# 👤 用户初始化路由：处理用户画像和 AI 助手定制
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.llm.base import BaseLLMProvider
from api.dependencies import get_llm_service
from services.profile_service import ProfileService
from schemas.onboarding_schema import (
    OnboardingRequest,
    OnboardingResponse,
    ProfileUpdateRequest,
    AICustomizationUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/user", tags=["用户初始化"])


@router.post("/onboarding", response_model=OnboardingResponse)
async def onboarding(
    request: OnboardingRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    """用户初始化

    流程：
    1. 创建用户
    2. 生成 user_prompt_template（精简版）
    3. 生成 agent_persona_template（AI 人设）
    4. 创建固定分类（4 个）+ 动态领域分类（2 个）
    5. 将完整画像存入"核心自我"分类
    """
    logger.info(f"用户初始化请求: username={request.username}, identity_type={request.identity_type}")
    service = ProfileService(session, llm)
    result = await service.onboarding(request)

    if not result.success:
        logger.warning(f"用户初始化失败: username={request.username}, reason={result.message}")
        raise HTTPException(status_code=500, detail=result.message)

    logger.info(f"用户初始化成功: user_id={result.user_id}, username={request.username}")
    return result


@router.put("/profile")
async def update_profile(
    request: ProfileUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    """更新用户画像

    会重新生成 user_prompt_template 并存入数据库
    """
    logger.info(f"更新用户画像请求: user_id={request.user_id}")
    service = ProfileService(session, llm)
    result = await service.update_profile(request)

    if not result.get("success"):
        logger.warning(f"更新用户画像失败: user_id={request.user_id}, reason={result.get('message')}")
        raise HTTPException(status_code=404, detail=result.get("message", "更新失败"))

    logger.info(f"用户画像更新成功: user_id={request.user_id}")
    return result


@router.put("/ai-customization")
async def update_ai_customization(
    request: AICustomizationUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    """更新 AI 助手定制

    会重新生成 agent_persona_template 并存入数据库
    """
    logger.info(f"更新 AI 定制请求: user_id={request.user_id}")
    service = ProfileService(session, llm)
    result = await service.update_ai_customization(request)

    if not result.get("success"):
        logger.warning(f"更新 AI 定制失败: user_id={request.user_id}, reason={result.get('message')}")
        raise HTTPException(status_code=404, detail=result.get("message", "更新失败"))

    logger.info(f"AI 定制更新成功: user_id={request.user_id}")
    return result
