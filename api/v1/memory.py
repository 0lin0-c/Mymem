import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.memory_schema import ForgetRequest, UpdateAtomicItemRequest, UpdateMemoryRequest
from services.llm import LLMFactory
from services.memory import MemoryLifecycle
from services.memory_admin_service import MemoryAdminService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/memory", tags=["记忆管理"])


@router.get("/atomic-items")
async def get_atomic_items(
    user_id: str,
    category_name: str | None = None,
    limit: int = 50,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    return {
        "atomic_items": await service.get_atomic_items(
            user_id=user_id,
            category_name=category_name,
            limit=limit,
        )
    }


@router.get("/category-stats")
async def get_category_stats(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    return {"success": True, "stats": await service.get_category_stats(user_id)}


@router.get("/resources")
async def get_resources(
    user_id: str,
    limit: int = 20,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    return {"resources": await service.get_resources(user_id, limit=limit)}


@router.get("/resources/{resource_id}")
async def get_resource_detail(
    resource_id: str,
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    detail = await service.get_resource_detail(resource_id, user_id)
    if not detail:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return detail


@router.get("/stats")
async def get_memory_stats(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    llm = LLMFactory.get_provider()
    lifecycle = MemoryLifecycle(session, llm)
    stats = await lifecycle.get_memory_stats(user_id)
    return {"success": True, **stats}


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    if not await service.delete_resource(resource_id, user_id):
        raise HTTPException(status_code=404, detail="记忆不存在或无权删除")
    return {"success": True, "message": "Conversation summary deleted"}


@router.delete("/atomic-items/{item_id}")
async def delete_atomic_item(
    item_id: str,
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    if not await service.delete_atomic_item(item_id, user_id):
        raise HTTPException(status_code=404, detail="记忆不存在或无权删除")
    return {"success": True, "message": "Atomic memory deleted"}


@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: str,
    request: UpdateMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    if not await service.update_resource(
        resource_id=resource_id,
        user_id=request.user_id,
        description=request.description,
        importance_score=request.importance_score,
    ):
        raise HTTPException(status_code=404, detail="记忆不存在或无权修改")
    return {"success": True, "message": "Conversation summary updated"}


@router.put("/atomic-items/{item_id}")
async def update_atomic_item(
    item_id: str,
    request: UpdateAtomicItemRequest,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = MemoryAdminService(session)
    if not await service.update_atomic_item(
        item_id=item_id,
        user_id=request.user_id,
        content=request.content,
        importance_score=request.importance_score,
    ):
        raise HTTPException(status_code=404, detail="记忆不存在或无权修改")
    return {"success": True, "message": "Atomic memory updated"}


@router.post("/forget")
async def forget_low_importance(
    request: ForgetRequest,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    logger.info(
        "Forgetting low-importance memories: user_id=%s threshold=%s",
        request.user_id,
        request.threshold,
    )
    llm = LLMFactory.get_provider()
    lifecycle = MemoryLifecycle(session, llm)
    deleted = await lifecycle.forget_low_importance(
        user_id=request.user_id,
        threshold=request.threshold,
    )
    await session.commit()
    return {
        "success": True,
        "deleted_categories": deleted.get("categories", 0),
        "message": f"Cleaned {deleted.get('categories', 0)} low-importance memories",
    }


@router.post("/decay")
async def decay_importance(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    llm = LLMFactory.get_provider()
    lifecycle = MemoryLifecycle(session, llm)
    updated = await lifecycle.decay_importance(user_id)
    await session.commit()
    return {
        "success": True,
        "updated_resources": updated.get("resources", 0),
        "updated_categories": updated.get("categories", 0),
        "message": f"Updated importance for {updated.get('categories', 0)} atomic memories",
    }
