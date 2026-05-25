import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.llm_settings_schema import LLMSettingsRequest, LLMSettingsResponse
from services.llm_settings_service import LLMSettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/user", tags=["LLM设置"])


@router.put("/llm-settings", response_model=LLMSettingsResponse)
async def update_llm_settings(
    request: LLMSettingsRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    logger.info(
        "Update LLM settings request: user_id=%s provider=%s",
        request.user_id,
        request.llm_provider,
    )
    service = LLMSettingsService(session)
    updated = await service.update_settings(
        user_id=request.user_id,
        llm_provider=request.llm_provider,
        llm_api_key=request.llm_api_key,
        llm_base_url=request.llm_base_url,
        llm_model=request.llm_model,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="用户不存在")

    return LLMSettingsResponse(
        success=True,
        message="LLM 配置已保存，正在预热...",
        warmed_up=False,
    )


@router.get("/llm-settings/{user_id}")
async def get_llm_settings(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    service = LLMSettingsService(session)
    settings = await service.get_settings(user_id)
    if not settings:
        raise HTTPException(status_code=404, detail="用户不存在")
    return settings
