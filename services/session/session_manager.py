# 🔧 会话状态管理器
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

from services.session.state import SessionState, PendingChat


@dataclass
class FlushableSession:
    """可落库的会话数据"""
    session_id: str
    user_id: str
    user_name: Optional[str]
    pending_chats: List[PendingChat]


class SessionManager:
    """会话管理器 - 内存实现

    职责：
    1. 创建/获取/销毁会话
    2. 管理会话状态（用户识别、chat计数、pending队列）
    3. 会话超时清理
    """

    def __init__(self, session_timeout_minutes: int = 30):
        self._sessions: dict[str, SessionState] = {}
        self._timeout = session_timeout_minutes

    def create_session(self, session_id: str) -> SessionState:
        """创建新会话"""
        state = SessionState(session_id=session_id)
        self._sessions[session_id] = state
        logger.debug(f"创建新会话: session_id={session_id}")
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取会话，不存在返回 None"""
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> SessionState:
        """获取或创建会话"""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        session.touch()
        return session

    def destroy_session(self, session_id: str) -> bool:
        """销毁会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"销毁会话: session_id={session_id}")
            return True
        return False

    def add_pending_chat(
        self,
        session_id: str,
        user_input: str,
        assistant_response: str,
    ) -> SessionState:
        """添加待存储的对话"""
        session = self.get_or_create(session_id)
        session.pending_chats.append(PendingChat(
            user_input=user_input,
            assistant_response=assistant_response,
        ))
        session.chat_count += 1
        return session

    def clear_pending_chats(self, session_id: str) -> list[PendingChat]:
        """清空并返回待存储对话"""
        session = self.get_session(session_id)
        if session is None:
            return []

        chats = session.pending_chats.copy()
        session.pending_chats.clear()
        session.chat_count = 0
        return chats

    def set_user(self, session_id: str, user_id: str, user_name: str) -> SessionState:
        """设置会话的用户身份"""
        session = self.get_or_create(session_id)
        session.user_id = user_id
        session.user_name = user_name
        session.is_identified = True
        return session

    def cleanup_expired(self) -> int:
        """清理过期会话，返回清理数量"""
        threshold = datetime.now() - timedelta(minutes=self._timeout)
        expired = [
            sid for sid, state in self._sessions.items()
            if state.last_active_at < threshold
        ]

        for sid in expired:
            del self._sessions[sid]

        if expired:
            logger.info(f"清理过期会话: 数量={len(expired)}")
        return len(expired)

    def get_expired_sessions_with_pending(
        self,
        timeout_minutes: int = 30,
    ) -> List[FlushableSession]:
        """找出过期且有待存储对话的会话

        Args:
            timeout_minutes: 超时分钟数，默认使用 SessionManager 的超时设置

        Returns:
            FlushableSession 列表，包含 session_id, user_id, user_name, pending_chats
        """
        timeout = timeout_minutes or self._timeout
        threshold = datetime.now() - timedelta(minutes=timeout)

        flushable = []
        for sid, state in self._sessions.items():
            # 检查：过期 + 已识别用户 + 有待存储对话
            if (
                state.last_active_at < threshold
                and state.is_identified
                and state.pending_chats
            ):
                flushable.append(FlushableSession(
                    session_id=sid,
                    user_id=state.user_id,
                    user_name=state.user_name,
                    pending_chats=state.pending_chats.copy(),
                ))

        return flushable

    def mark_flushed(self, session_id: str) -> bool:
        """成功落库后清除 pending_chats

        Args:
            session_id: 会话 ID

        Returns:
            是否成功清除
        """
        session = self.get_session(session_id)
        if session is None:
            return False

        session.pending_chats.clear()
        session.chat_count = 0
        return True

    def get_and_clear_pending(
        self,
        session_id: str,
    ) -> Tuple[List[PendingChat], Optional[str], Optional[str]]:
        """原子操作：获取并清除待存储对话（用于关键词触发）

        Args:
            session_id: 会话 ID

        Returns:
            (pending_chats, user_id, user_name) 元组
        """
        session = self.get_session(session_id)
        if session is None:
            return [], None, None

        chats = session.pending_chats.copy()
        session.pending_chats.clear()
        session.chat_count = 0

        return chats, session.user_id, session.user_name


# 全局单例
session_manager = SessionManager()
