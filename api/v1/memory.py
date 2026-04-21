# 🧠 记忆管理路由：查看和管理用户的记忆数据
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from tables import Category, Resource, ResourceCategory
from repositories import ResourceRepository, CategoryRepository, ResourceCategoryRepository
from services.llm import LLMFactory
from services.memory import MemoryLifecycle
from schemas.memory_schema import (
    DeleteMemoryRequest,
    DeleteAtomicItemRequest,
    UpdateMemoryRequest,
    UpdateAtomicItemRequest,
    ForgetRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/memory", tags=["记忆管理"])


# ========== 查询接口 ==========

@router.get("/atomic-items")
async def get_atomic_items(
    user_id: str,
    category_name: Optional[str] = None,
    limit: int = 50,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取用户的原子化记忆（Category 表）"""
    logger.debug(f"获取原子化记忆: user_id={user_id}, category_name={category_name}, limit={limit}")
    query = select(Category).where(Category.user_id == user_id)

    if category_name:
        query = query.where(Category.category_name == category_name)

    query = query.order_by(Category.importance_score.desc(), Category.created_at.desc()).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()
    logger.debug(f"查询到 {len(items)} 条原子化记忆")

    return {
        "atomic_items": [
            {
                "id": item.id,
                "category_name": item.category_name,
                "content": item.content,
                "importance_score": item.importance_score,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]
    }


@router.get("/category-stats")
async def get_category_stats(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """获取各分类的统计信息"""
    logger.debug(f"获取分类统计: user_id={user_id}")
    repo = CategoryRepository(session)
    stats = await repo.get_category_stats(user_id)
    return {"success": True, "stats": stats}


@router.get("/resources")
async def get_resources(
    user_id: str,
    limit: int = 20,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取用户的对话摘要（Resource 表）"""
    logger.debug(f"获取资源列表: user_id={user_id}, limit={limit}")
    result = await session.execute(
        select(Resource)
        .where(Resource.user_id == user_id)
        .order_by(Resource.created_at.desc())
        .limit(limit)
    )
    resources = result.scalars().all()
    logger.debug(f"查询到 {len(resources)} 条资源")
    return {
        "resources": [
            {
                "id": r.id,
                "modality": r.modality,
                "description": r.description,
                "assistant_response": r.assistant_response,
                "importance_score": r.importance_score,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in resources
        ]
    }


@router.get("/resources/{resource_id}")
async def get_resource_detail(
    resource_id: str,
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """获取单个对话摘要的详情"""
    logger.debug(f"获取资源详情: resource_id={resource_id}, user_id={user_id}")
    result = await session.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.user_id == user_id,
        )
    )
    resource = result.scalar_one_or_none()

    if not resource:
        logger.warning(f"获取资源详情失败: 资源不存在, resource_id={resource_id}")
        raise HTTPException(status_code=404, detail="记忆不存在")

    # 通过 resource_categories 关联表获取关联的原子化信息
    cat_result = await session.execute(
        select(Category)
        .join(ResourceCategory, ResourceCategory.category_id == Category.id)
        .where(ResourceCategory.resource_id == resource_id)
    )
    atomic_items = cat_result.scalars().all()

    return {
        "id": resource.id,
        "modality": resource.modality,
        "raw_content": resource.raw_content,
        "description": resource.description,
        "assistant_response": resource.assistant_response,
        "importance_score": resource.importance_score,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "atomic_items": [
            {
                "id": item.id,
                "category_name": item.category_name,
                "content": item.content,
                "importance_score": item.importance_score,
            }
            for item in atomic_items
        ],
    }


# ========== 统计接口 ==========

@router.get("/stats")
async def get_memory_stats(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """获取记忆库统计信息"""
    llm = LLMFactory.get_provider()
    lifecycle = MemoryLifecycle(session, llm)

    stats = await lifecycle.get_memory_stats(user_id)
    return {"success": True, **stats}


# ========== 管理接口 ==========

@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """删除对话摘要及其关联的原子化信息"""
    logger.info(f"删除资源请求: resource_id={resource_id}, user_id={user_id}")
    resource_repo = ResourceRepository(session)
    resource = await resource_repo.get_by_id(resource_id)

    if not resource or resource.user_id != user_id:
        logger.warning(f"删除资源失败: 资源不存在或无权删除, resource_id={resource_id}")
        raise HTTPException(status_code=404, detail="记忆不存在或无权删除")

    # 删除关联表记录
    rc_repo = ResourceCategoryRepository(session)
    await rc_repo.delete_by_resource(resource_id)

    # 删除资源
    await resource_repo.delete(resource_id)

    await session.commit()
    logger.info(f"资源删除成功: resource_id={resource_id}")
    return {"success": True, "message": "Conversation summary deleted"}


@router.delete("/atomic-items/{item_id}")
async def delete_atomic_item(
    item_id: str,
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """删除单条原子化记忆"""
    logger.info(f"删除原子化记忆请求: item_id={item_id}, user_id={user_id}")
    category_repo = CategoryRepository(session)
    item = await category_repo.get_by_id(item_id)

    if not item or item.user_id != user_id:
        logger.warning(f"删除原子化记忆失败: 不存在或无权限, item_id={item_id}")
        raise HTTPException(status_code=404, detail="记忆不存在或无权删除")

    await category_repo.delete(item_id)
    await session.commit()
    logger.info(f"原子化记忆删除成功: item_id={item_id}")
    return {"success": True, "message": "Atomic memory deleted"}


@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: str,
    request: UpdateMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """更新对话摘要"""
    logger.info(f"更新资源请求: resource_id={resource_id}, user_id={request.user_id}")
    resource_repo = ResourceRepository(session)
    resource = await resource_repo.get_by_id(resource_id)

    if not resource or resource.user_id != request.user_id:
        logger.warning(f"更新资源失败: 不存在或无权限, resource_id={resource_id}")
        raise HTTPException(status_code=404, detail="记忆不存在或无权修改")

    # 更新内容
    update_data = {"description": request.description}
    if request.importance_score is not None:
        update_data["importance_score"] = request.importance_score

    await resource_repo.update(resource_id, **update_data)
    await session.commit()
    logger.info(f"资源更新成功: resource_id={resource_id}")
    return {"success": True, "message": "Conversation summary updated"}


@router.put("/atomic-items/{item_id}")
async def update_atomic_item(
    item_id: str,
    request: UpdateAtomicItemRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """更新原子化记忆"""
    logger.info(f"更新原子化记忆请求: item_id={item_id}, user_id={request.user_id}")
    category_repo = CategoryRepository(session)
    item = await category_repo.get_by_id(item_id)

    if not item or item.user_id != request.user_id:
        logger.warning(f"更新原子化记忆失败: 不存在或无权限, item_id={item_id}")
        raise HTTPException(status_code=404, detail="记忆不存在或无权修改")

    # 更新内容
    update_data = {"content": request.content}
    if request.importance_score is not None:
        update_data["importance_score"] = request.importance_score

    await category_repo.update(item_id, **update_data)
    await session.commit()
    logger.info(f"原子化记忆更新成功: item_id={item_id}")
    return {"success": True, "message": "Atomic memory updated"}


@router.post("/forget")
async def forget_low_importance(
    request: ForgetRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """清理低重要性记忆（遗忘机制）"""
    logger.info(f"执行遗忘机制: user_id={request.user_id}, threshold={request.threshold}")
    llm = LLMFactory.get_provider()
    lifecycle = MemoryLifecycle(session, llm)

    deleted = await lifecycle.forget_low_importance(
        user_id=request.user_id,
        threshold=request.threshold,
    )

    await session.commit()
    logger.info(f"遗忘机制完成: 删除 {deleted.get('categories', 0)} 条记忆")
    return {
        "success": True,
        "deleted_categories": deleted.get("categories", 0),
        "message": f"Cleaned {deleted.get('categories', 0)} low-importance memories",
    }


@router.post("/decay")
async def decay_importance(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """执行重要性衰减"""
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
