# 💬 对话路由：处理用户对话，集成会话管理和缓存机制
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from api.dependencies import get_llm_service
from services.llm.base import BaseLLMProvider
from services.llm.user_llm_factory import UserLLMFactory
from repositories import UserRepository
from services.memory import MemoryWriter
from services.chat_orchestrator import ChatOrchestrator
from services.session import session_manager, UserIdentifier, flush_session_immediately
from services.session.flush_service import _generate_batch_summary
from schemas.chat_schema import ChatRequest, SaveMemoryRequest, SaveMemoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["对话"])

# chat 模态累积多少轮后存储
CHAT_BATCH_SIZE = 5

# 立即落库关键词
IMMEDIATE_FLUSH_KEYWORDS = ["再见", "晚安", "拜拜", "bye", "goodbye", "byebye"]


def should_flush_immediately(query: str) -> bool:
    """检测用户是否表示结束对话"""
    query_lower = query.lower().strip()
    return any(keyword in query_lower for keyword in IMMEDIATE_FLUSH_KEYWORDS)


@router.post("")
async def chat(
    request: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    流式处理用户对话

    响应格式（NDJSON，每行一个 JSON）：
    - 流式内容：{"type": "content", "text": "..."}
    - 结束标记：{"type": "done", "user_id": "...", "user_name": "...", ...}

    流程:
    1. 获取或创建会话状态
    2. 检查用户是否已识别（user_id 直接识别 或 LLM 引导识别）
    3. LLM 流式生成回复
    4. 根据 modality 决定是否立即存储或缓存
    """
    # 获取用户级 LLM 配置
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(request.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取 LLM 客户端：优先使用用户配置，否则使用全局配置
    if user.llm_provider and user.llm_api_key:
        # 用户级 LLM
        logger.info(f"使用用户级 LLM: user_id={user.id}")
        logger.debug(f"用户 LLM 配置: provider={user.llm_provider}, model={user.llm_model}")
        llm = UserLLMFactory.get_or_create(
            user_id=user.id,
            provider=user.llm_provider,
            api_key=user.llm_api_key,
            base_url=user.llm_base_url,
            model=user.llm_model,
        )
    else:
        # 全局 LLM（从环境变量读取）
        from services.llm.factory import LLMFactory
        logger.info(f"使用全局 LLM: user_id={user.id}")
        llm = LLMFactory.get_provider()
    async def generate():
        try:
            # ========== Step 1: 获取会话状态 ==========
            session_state = session_manager.get_or_create(request.session_id)
            logger.debug(f"获取会话状态: session_id={request.session_id}, is_identified={session_state.is_identified}")

            # ========== Step 2: 用户识别 ==========
            # 优先使用请求中的 user_id（有前端登录时）
            if request.user_id and not session_state.is_identified:
                from tables import User
                user = await session.get(User, request.user_id)
                if user:
                    session_manager.set_user(
                        request.session_id,
                        request.user_id,
                        user.username,
                    )
                    logger.info(f"用户识别成功(前端登录): user_id={request.user_id}, username={user.username}")

            # 如果仍未识别，走 LLM 引导识别（无前端/CLI 场景）
            if not session_state.is_identified:
                logger.debug(f"尝试 LLM 引导识别: session_id={request.session_id}")
                identifier = UserIdentifier(llm, session)
                id_result = await identifier.identify_or_ask(session_state, request.query)

                if id_result["identified"]:
                    session_manager.set_user(
                        request.session_id,
                        id_result["user_id"],
                        id_result["user_name"],
                    )
                    logger.info(f"LLM 引导识别成功: user_id={id_result['user_id']}, user_name={id_result['user_name']}")

                # 识别询问直接返回
                if id_result["response"]:
                    yield json.dumps({
                        "type": "content",
                        "text": id_result["response"],
                    }, ensure_ascii=False) + "\n"
                    yield json.dumps({
                        "type": "done",
                        "user_id": id_result.get("user_id"),
                        "user_name": id_result.get("user_name"),
                        "is_identified": id_result["identified"],
                    }, ensure_ascii=False) + "\n"
                    return

            # ========== Step 3: 流式生成回复 ==========
            from tables import User
            user = await session.get(User, session_state.user_id)

            # 流式输出
            full_answer = []
            try:
                orchestrator = ChatOrchestrator(session=session, llm=llm)
                async for chunk in orchestrator.stream(
                    user_id=session_state.user_id,
                    user_query=request.query,
                    user_prompt_template=user.user_prompt_template if user else None,
                    agent_persona_template=user.agent_persona_template if user else None,
                    pending_chats=session_state.pending_chats,
                    top_k=5,
                ):
                    full_answer.append(chunk)
                    yield json.dumps({"type": "content", "text": chunk}, ensure_ascii=False) + "\n"
            except Exception as e:
                error_msg = f"Sorry, I encountered a problem: {str(e)}"
                logger.error(f"LLM 流式输出失败: {type(e).__name__}: {e}")
                yield json.dumps({"type": "content", "text": error_msg}, ensure_ascii=False) + "\n"
                full_answer = [error_msg]

            answer = "".join(full_answer)

            # ========== Step 4: 处理存储逻辑 ==========
            metadata = {}
            if request.modality == "text":
                session_manager.add_pending_chat(
                    request.session_id,
                    request.query,
                    answer,
                )
                logger.debug(f"添加待存储对话: session_id={request.session_id}, chat_count={session_state.chat_count}")

                if should_flush_immediately(request.query):
                    import asyncio
                    asyncio.create_task(flush_session_immediately(request.session_id))
                    metadata["flushed"] = True
                    logger.info(f"检测到结束关键词，触发立即落库: session_id={request.session_id}")
                elif session_state.chat_count >= CHAT_BATCH_SIZE:
                    logger.info(f"对话累积达到 {CHAT_BATCH_SIZE} 轮，触发批量存储")
                    result = await _batch_save(session, llm, session_state)
                    metadata["resource_id"] = result.get("resource_id")
                    metadata["category_name"] = result.get("category_name")
                    metadata["importance_score"] = result.get("importance_score")

            # 输出结束标记
            yield json.dumps({
                "type": "done",
                "user_id": session_state.user_id,
                "user_name": session_state.user_name,
                "is_identified": True,
                **metadata,
            }, ensure_ascii=False) + "\n"

        except Exception as e:
            logger.exception(f"对话处理异常: {type(e).__name__}: {e}")
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"

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
    """批量存储累积的对话"""
    pending_chats = session_manager.clear_pending_chats(session_state.session_id)

    if not pending_chats:
        return {}

    combined_input = "\n\n".join([
        f"用户: {chat.user_input}\n助手: {chat.assistant_response}"
        for chat in pending_chats
    ])

    summary = await _generate_batch_summary(llm, pending_chats)

    writer = MemoryWriter(session, llm)
    result = await writer.save_chat(
        user_id=session_state.user_id,
        user_input=combined_input,
        assistant_response=summary,
        modality="text",
    )

    return result


@router.post("/save", response_model=SaveMemoryResponse)
async def save_memory(
    request: SaveMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[BaseLLMProvider, Depends(get_llm_service)],
):
    """直接保存对话到记忆（不生成回复）"""
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

    except ValueError as e:
        logger.warning(f"保存记忆失败(参数错误): {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"保存记忆失败: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
