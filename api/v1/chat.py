import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_llm_service
from core.database import get_db
from schemas.chat_schema import ChatRequest, SaveMemoryRequest, SaveMemoryResponse
from services.chat_orchestrator import ChatOrchestrator
from services.llm.base import BaseLLMProvider
from services.memory import MemoryWriter
from services.session import UserIdentifier, flush_session_immediately, session_manager
from services.session.flush_service import _generate_batch_summary
from services.user_account_service import UserAccountService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["对话"])

CHAT_BATCH_SIZE = 5
IMMEDIATE_FLUSH_KEYWORDS = ["再见", "晚安", "拜拜", "bye", "goodbye", "byebye"]


@router.get("")
async def chat_get_not_allowed():
    raise HTTPException(status_code=405, detail="Method Not Allowed")


def should_flush_immediately(query: str) -> bool:
    query_lower = query.lower().strip()
    return any(keyword in query_lower for keyword in IMMEDIATE_FLUSH_KEYWORDS)


@router.post("")
async def chat(
    request: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    account_service = UserAccountService(session)
    request_user, llm = await account_service.get_user_llm_context(request.user_id)
    if request.user_id and not request_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    async def generate():
        try:
            session_state = session_manager.get_or_create(request.session_id)
            logger.debug(
                "Loaded chat session: session_id=%s is_identified=%s",
                request.session_id,
                session_state.is_identified,
            )

            if request.user_id and not session_state.is_identified:
                session_manager.set_user(
                    request.session_id,
                    request.user_id,
                    request_user.username,
                )
                logger.info(
                    "User identified from request: user_id=%s username=%s",
                    request.user_id,
                    request_user.username,
                )

            if not session_state.is_identified:
                identifier = UserIdentifier(llm, session)
                id_result = await identifier.identify_or_ask(session_state, request.query)

                if id_result["identified"]:
                    session_manager.set_user(
                        request.session_id,
                        id_result["user_id"],
                        id_result["user_name"],
                    )

                if id_result["response"]:
                    yield json.dumps(
                        {
                            "type": "content",
                            "text": id_result["response"],
                        },
                        ensure_ascii=False,
                    ) + "\n"
                    yield json.dumps(
                        {
                            "type": "done",
                            "user_id": id_result.get("user_id"),
                            "user_name": id_result.get("user_name"),
                            "is_identified": id_result["identified"],
                        },
                        ensure_ascii=False,
                    ) + "\n"
                    return

            active_user = request_user
            if session_state.user_id and (
                not request_user or session_state.user_id != request_user.id
            ):
                active_user = await account_service.get_user(session_state.user_id)

            full_answer = []
            try:
                orchestrator = ChatOrchestrator(session=session, llm=llm)
                async for chunk in orchestrator.stream(
                    user_id=session_state.user_id,
                    user_query=request.query,
                    user_prompt_template=active_user.user_prompt_template if active_user else None,
                    agent_persona_template=active_user.agent_persona_template if active_user else None,
                    pending_chats=session_state.pending_chats,
                    top_k=10,
                ):
                    full_answer.append(chunk)
                    yield json.dumps(
                        {"type": "content", "text": chunk},
                        ensure_ascii=False,
                    ) + "\n"
            except Exception as exc:
                error_msg = f"Sorry, I encountered a problem: {exc}"
                logger.error("LLM stream failed: %s: %s", type(exc).__name__, exc)
                yield json.dumps(
                    {"type": "content", "text": error_msg},
                    ensure_ascii=False,
                ) + "\n"
                full_answer = [error_msg]

            answer = "".join(full_answer)
            metadata = {}

            if request.modality == "text":
                session_manager.add_pending_chat(
                    request.session_id,
                    request.query,
                    answer,
                )

                if should_flush_immediately(request.query):
                    asyncio.create_task(flush_session_immediately(request.session_id))
                    metadata["flushed"] = True
                elif session_state.chat_count >= CHAT_BATCH_SIZE:
                    result = await _batch_save(session, llm, session_state)
                    metadata["resource_id"] = result.get("resource_id")
                    metadata["category_name"] = result.get("category_name")
                    metadata["importance_score"] = result.get("importance_score")

            yield json.dumps(
                {
                    "type": "done",
                    "user_id": session_state.user_id,
                    "user_name": session_state.user_name,
                    "is_identified": True,
                    **metadata,
                },
                ensure_ascii=False,
            ) + "\n"

        except Exception as exc:
            logger.exception("Chat handling failed: %s: %s", type(exc).__name__, exc)
            yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _batch_save(
    session: AsyncSession,
    llm: BaseLLMProvider,
    session_state,
) -> dict:
    pending_chats = session_manager.clear_pending_chats(session_state.session_id)
    if not pending_chats:
        return {}

    combined_input = "\n\n".join([
        f"用户: {chat.user_input}\n助手: {chat.assistant_response}"
        for chat in pending_chats
    ])
    summary = await _generate_batch_summary(llm, pending_chats)

    writer = MemoryWriter(session, llm)
    return await writer.save_chat(
        user_id=session_state.user_id,
        user_input=combined_input,
        assistant_response=summary,
        modality="text",
    )


@router.post("/save", response_model=SaveMemoryResponse)
async def save_memory(
    request: SaveMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    try:
        writer = MemoryWriter(session, llm)
        result = await writer.save_chat(
            user_id=request.user_id,
            user_input=request.user_input,
            assistant_response=request.assistant_response,
            modality=request.modality,
        )

        first_item = result["atomic_items"][0] if result.get("atomic_items") else {}
        return SaveMemoryResponse(
            success=True,
            resource_id=result["resource_id"],
            category_name=first_item.get("category_name"),
            category_id=first_item.get("id"),
            importance_score=result.get("importance_score"),
            message="记忆保存成功",
        )

    except ValueError as exc:
        logger.warning("Save memory failed with bad input: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Save memory failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}")
