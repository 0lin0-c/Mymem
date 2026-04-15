# 🔍 检索路由：提供记忆检索 API 端点
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.llm.base import BaseLLMProvider
from api.dependencies import get_llm_service
from services.retrieval.retriever import MemoryRetriever
from schemas.retrieve_schema import (
    RetrieveRequest,
    RetrieveResponse,
    RetrieveResultItem,
    RetrieveStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/retrieve", tags=["检索"])


@router.post("", response_model=RetrieveResponse)
async def retrieve_memories(
    request: RetrieveRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    """
    检索相关记忆

    流程:
    1. LLM 分类判断：分析 query 属于哪些分类
    2. 分类内检索：只在 LLM 指定的类别中检索
    3. 向量兜底：如果分类结果不足，使用向量全局检索
    4. 返回检索结果和上下文文本
    """
    logger.info(f"检索请求: user_id={request.user_id}, top_k={request.top_k}")
    logger.debug(f"检索查询内容: query={request.query[:100]}...")
    try:
        # 创建检索器
        retriever = MemoryRetriever(session, llm)

        # Step 1: 执行检索（内部已包含 LLM 分类判断）
        results = await retriever.retrieve(
            user_id=request.user_id,
            query=request.query,
            top_k=request.top_k,
            use_llm_classification=True,
        )

        # Step 2: 从结果中提取检测到的分类
        categories_detected = list({
            r["category"].category_name
            for r in results
            if r.get("category")
        })
        logger.info(f"检索完成: 检测到分类={categories_detected}, 结果数={len(results)}")

        # Step 3: 用已有结果构建上下文文本（避免重复检索）
        context_text = await retriever.build_context_from_results(results)

        # Step 4: 转换结果格式
        result_items = []
        for result in results:
            resource = result.get("resource")
            category = result.get("category")

            if resource:
                result_items.append(RetrieveResultItem(
                    resource_id=resource.id,
                    description=resource.description or "",
                    category_name=category.category_name if category else None,
                    importance_score=resource.importance_score,
                    retrieval_score=result.get("score", 0),
                    created_at=resource.created_at,
                ))

        return RetrieveResponse(
            categories_detected=categories_detected,
            results=result_items,
            total=len(result_items),
            context_text=context_text,
        )

    except ValueError as e:
        logger.warning(f"检索失败(参数错误): {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"检索失败: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


@router.get("/stats", response_model=RetrieveStatsResponse)
async def get_retrieve_stats(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    获取检索统计信息

    用于优化检索策略和了解用户记忆分布
    """
    try:
        from repositories import CategoryRepository, ResourceRepository

        category_repo = CategoryRepository(session)
        resource_repo = ResourceRepository(session)

        # 获取分类分布
        category_stats = await category_repo.get_category_stats(user_id)

        # 获取资源总数
        resources = await resource_repo.get_by_user_id(user_id, limit=1000)
        total_resources = len(resources)

        # 计算平均重要性
        avg_importance = 0.0
        if resources:
            total_importance = sum(r.importance_score for r in resources)
            avg_importance = total_importance / len(resources)

        # 构建分类分布
        category_distribution = {
            name: {
                "count": stats["count"],
                "avg_importance": stats["avg_importance"],
            }
            for name, stats in category_stats.items()
        }

        return RetrieveStatsResponse(
            total_retrievals=total_resources,
            avg_results_per_query=avg_importance,
            category_distribution=category_distribution,
            avg_latency_ms=0.0,  # 需要在实际检索中记录
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
