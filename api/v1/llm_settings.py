# ⚙️ LLM 设置路由：处理用户 LLM 配置和预热
import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from repositories import UserRepository
from schemas.llm_settings_schema import LLMSettingsRequest, LLMSettingsResponse
from services.llm.user_llm_factory import UserLLMFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/user", tags=["LLM设置"])


@router.put("/llm-settings", response_model=LLMSettingsResponse)
async def update_llm_settings(
    request: LLMSettingsRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """更新用户 LLM 配置并预热

    流程：
    1. 保存 LLM 配置到用户表
    2. 后台预热 LLM 连接
    3. 生成动态分类（如果尚未生成）
    """
    logger.info(f"更新 LLM 配置请求: user_id={request.user_id}, provider={request.llm_provider}")
    user_repo = UserRepository(session)

    # 检查用户是否存在
    user = await user_repo.get_by_id(request.user_id)
    if not user:
        logger.warning(f"更新 LLM 配置失败: 用户不存在, user_id={request.user_id}")
        raise HTTPException(status_code=404, detail="用户不存在")

    # 更新 LLM 配置
    await user_repo.update(
        request.user_id,
        llm_provider=request.llm_provider,
        llm_api_key=request.llm_api_key,
        llm_base_url=request.llm_base_url,
        llm_model=request.llm_model,
        llm_warmed_up=False,
    )

    await session.commit()

    # 清除旧的 LLM 客户端缓存（如果有）
    UserLLMFactory.remove(request.user_id)

    # 后台预热 LLM
    asyncio.create_task(
        _warmup_and_generate_categories(
            request.user_id,
            request.llm_provider,
            request.llm_api_key,
            request.llm_base_url,
            request.llm_model,
        )
    )

    logger.info(f"LLM 配置已保存，开始预热: user_id={request.user_id}")
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
    """获取用户 LLM 配置状态"""
    logger.debug(f"获取 LLM 配置: user_id={user_id}")
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if not user:
        logger.warning(f"获取 LLM 配置失败: 用户不存在, user_id={user_id}")
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "configured": bool(user.llm_provider and user.llm_api_key),
        "llm_provider": user.llm_provider,
        "llm_base_url": user.llm_base_url,
        "llm_model": user.llm_model,
        "warmed_up": user.llm_warmed_up,
    }


async def _warmup_and_generate_categories(
    user_id: str,
    llm_provider: str,
    llm_api_key: str,
    llm_base_url: str | None,
    llm_model: str,
) -> None:
    """后台预热 LLM 并生成动态分类"""
    from core.database import AsyncSessionLocal
    from repositories import CategoryRepository

    try:
        # 创建用户专属 LLM 客户端
        llm = UserLLMFactory.get_or_create(
            user_id=user_id,
            provider=llm_provider,
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=llm_model,
        )

        # 预热：发送简单请求
        await llm.generate_chat_response(
            system_prompt="你是一个助手",
            context="",
            user_query="OK",
        )
        logger.info(f"用户 {user_id} LLM 预热完成")

        # 更新预热状态
        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            await user_repo.update(user_id, llm_warmed_up=True)
            await session.commit()

        # 生成动态分类（如果需要）
        async with AsyncSessionLocal() as session:
            category_repo = CategoryRepository(session)

            # 检查是否已有动态分类（非占位符）
            items = await category_repo.get_by_user_id(user_id)
            has_real_categories = any(
                "生成中" not in item.category_name for item in items
                if item.category_name not in ["核心自我", "情景时间轴", "语义知识库", "社交关系图谱"]
            )

            if not has_real_categories:
                # TODO: 调用 LLM 生成动态分类
                logger.info(f"用户 {user_id} 需要生成动态分类")
                # 这里需要获取用户的初始化请求，暂时跳过

    except Exception as e:
        logger.error(f"用户 {user_id} LLM 预热失败: {e}")
