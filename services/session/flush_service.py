# 🔄 会话自动落库服务：后台任务定期检查过期会话并落库
import asyncio
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.llm.base import BaseLLMProvider
from services.memory import MemoryWriter
from services.session import session_manager, FlushableSession

logger = logging.getLogger(__name__)

# 后台任务检查间隔（秒）
FLUSH_CHECK_INTERVAL = 600  # 10 分钟


async def flush_session_data(
    session: AsyncSession,
    llm: BaseLLMProvider,
    flushable: FlushableSession,
) -> bool:
    """将待存储对话写入数据库

    Args:
        session: 数据库会话
        llm: LLM 提供商
        flushable: 可落库的会话数据

    Returns:
        是否成功落库
    """
    if not flushable.pending_chats:
        return False

    try:
        # 合并对话为完整上下文
        combined_input = "\n\n".join([
            f"用户: {chat.user_input}\n助手: {chat.assistant_response}"
            for chat in flushable.pending_chats
        ])

        # 调用 LLM 生成综合摘要
        summary = await _generate_batch_summary(llm, flushable.pending_chats)

        # 存储到数据库
        writer = MemoryWriter(session, llm)
        result = await writer.save_chat(
            user_id=flushable.user_id,
            user_input=combined_input,
            assistant_response=summary,
            modality="text",
        )

        logger.info(
            f"自动落库成功: session_id={flushable.session_id}, "
            f"resource_id={result.get('resource_id')}, "
            f"rounds={len(flushable.pending_chats)}"
        )
        return True

    except Exception as e:
        logger.error(
            f"自动落库失败: session_id={flushable.session_id}, error={e}"
        )
        return False


async def _generate_batch_summary(llm: BaseLLMProvider, pending_chats: list) -> str:
    """调用 LLM 生成多轮对话的综合摘要

    Args:
        llm: LLM 提供商
        pending_chats: 待摘要的对话列表

    Returns:
        综合摘要文本
    """
    # Build conversation content
    conversation = "\n".join([
        f"Round {i+1}:\nUser: {chat.user_input}\nAssistant: {chat.assistant_response}"
        for i, chat in enumerate(pending_chats)
    ])

    prompt = f"""Generate a comprehensive summary for the following multi-turn conversation.

Conversation:
{conversation}

Requirements:
1. Use objective third-person narrative
2. Extract the core themes and key information from the conversation
3. Keep it concise, no more than 200 characters

Output only the summary, no additional explanation."""

    try:
        summary = await llm.generate_chat_response(
            system_prompt="You are a conversation summarization expert, skilled at extracting core information from multi-turn conversations.",
            context="",
            user_query=prompt,
        )
        return summary.strip()

    except Exception as e:
        # 降级：返回简单的统计摘要
        return f"Contains {len(pending_chats)} rounds of conversation"


async def auto_flush_background_task():
    """后台任务：定期检查过期会话并自动落库

    每 10 分钟检查一次，将超过 30 分钟无活动且有待存储对话的会话落库
    """
    logger.info("自动落库后台任务启动")

    while True:
        try:
            await asyncio.sleep(FLUSH_CHECK_INTERVAL)

            # 获取过期且有待存储对话的会话
            flushable_sessions = session_manager.get_expired_sessions_with_pending(
                timeout_minutes=30
            )

            if not flushable_sessions:
                continue

            logger.info(f"发现 {len(flushable_sessions)} 个待落库会话")

            # 获取 LLM 提供商
            llm = LLMFactory.get_provider()

            # 逐个处理落库
            async with AsyncSessionLocal() as session:
                for flushable in flushable_sessions:
                    success = await flush_session_data(session, llm, flushable)

                    if success:
                        # 清除内存中的 pending_chats
                        session_manager.mark_flushed(flushable.session_id)

                await session.commit()

        except asyncio.CancelledError:
            logger.info("自动落库后台任务被取消")
            break
        except Exception as e:
            logger.error(f"自动落库后台任务异常: {e}")
            # 继续运行，不中断


async def flush_session_immediately(
    session_id: str,
) -> bool:
    """立即落库指定会话（用于关键词触发）

    Args:
        session_id: 会话 ID

    Returns:
        是否成功落库
    """
    # 原子操作：获取并清除待存储对话
    pending_chats, user_id, user_name = session_manager.get_and_clear_pending(session_id)

    if not pending_chats or not user_id:
        return False

    try:
        # 获取 LLM 提供商
        llm = LLMFactory.get_provider()

        async with AsyncSessionLocal() as session:
            # 合并对话为完整上下文
            combined_input = "\n\n".join([
                f"用户: {chat.user_input}\n助手: {chat.assistant_response}"
                for chat in pending_chats
            ])

            # 调用 LLM 生成综合摘要
            summary = await _generate_batch_summary(llm, pending_chats)

            # 存储到数据库
            writer = MemoryWriter(session, llm)
            result = await writer.save_chat(
                user_id=user_id,
                user_input=combined_input,
                assistant_response=summary,
                modality="text",
            )

            await session.commit()

            logger.info(
                f"立即落库成功: session_id={session_id}, "
                f"resource_id={result.get('resource_id')}, "
                f"rounds={len(pending_chats)}"
            )
            return True

    except Exception as e:
        logger.error(f"立即落库失败: session_id={session_id}, error={e}")
        return False
