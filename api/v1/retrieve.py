import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_llm_service
from core.database import get_db
from schemas.retrieve_schema import (
    RetrieveRequest,
    RetrieveResponse,
    RetrieveResultItem,
    RetrieveStatsResponse,
)
from services.llm.base import BaseLLMProvider
from services.retrieval.retriever import MemoryRetriever
from services.retrieval_stats_service import RetrievalStatsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/retrieve", tags=["检索"])


@router.post("", response_model=RetrieveResponse)
async def retrieve_memories(
    request: RetrieveRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    logger.info("Retrieve request: user_id=%s top_k=%s", request.user_id, request.top_k)
    logger.debug("Retrieve query: query=%s", request.query[:100])
    try:
        retriever = MemoryRetriever(session, llm)
        results = await retriever.retrieve(
            user_id=request.user_id,
            query=request.query,
            top_k=request.top_k,
            use_llm_classification=True,
        )

        categories_detected = list({
            result["category"].category_name
            for result in results
            if result.get("category")
        })
        context_text = await retriever.build_context_from_results(results)

        result_items = []
        for result in results:
            resource = result.get("resource")
            category = result.get("category")
            if resource:
                result_items.append(
                    RetrieveResultItem(
                        resource_id=resource.id,
                        description=resource.description or "",
                        category_name=category.category_name if category else None,
                        importance_score=resource.importance_score,
                        retrieval_score=result.get("score", 0),
                        created_at=resource.created_at,
                    )
                )

        return RetrieveResponse(
            categories_detected=categories_detected,
            results=result_items,
            total=len(result_items),
            context_text=context_text,
        )

    except ValueError as exc:
        logger.warning("Retrieve failed with bad input: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Retrieve failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"检索失败: {exc}")


@router.get("/stats", response_model=RetrieveStatsResponse)
async def get_retrieve_stats(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        service = RetrievalStatsService(session)
        return RetrieveStatsResponse(**await service.get_stats(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {exc}")
