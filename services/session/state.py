# 📦 会话状态数据结构
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PendingChat:
    """待存储的单轮对话"""
    user_input: str
    assistant_response: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionState:
    """单个会话的完整状态"""
    session_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    chat_count: int = 0
    pending_chats: list[PendingChat] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_active_at: datetime = field(default_factory=datetime.now)

    # 用户识别相关
    identification_attempts: int = 0
    is_identified: bool = False

    def touch(self):
        """更新最后活跃时间"""
        self.last_active_at = datetime.now()
