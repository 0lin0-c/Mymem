# 🔄 Redis 分布式 Session 存储
import json
import logging
from datetime import datetime
from typing import Optional, List, Tuple

from services.session.state import SessionState, PendingChat

logger = logging.getLogger(__name__)


class RedisSessionStore:
    """Redis 分布式 Session 存储

    用于多实例部署场景，将 Session 状态存储在 Redis 中。

    优点：
    - 支持多实例水平扩展
    - Session 持久化
    - 支持集群部署

    数据结构：
    - session:{session_id} -> Hash (SessionState 字段)
    - session:{session_id}:pending -> List (PendingChat 列表)
    """

    def __init__(self, redis_url: Optional[str] = None):
        """初始化 Redis 连接

        Args:
            redis_url: Redis 连接 URL，如 redis://localhost:6379/0
        """
        from core.config import settings

        self.redis_url = redis_url or settings.redis_url
        self._redis = None

        if not self.redis_url:
            raise ValueError("Redis URL 未配置，请设置 REDIS_URL 环境变量")

    @property
    def redis(self):
        """延迟初始化 Redis 连接"""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError(
                    "请安装 redis 库: pip install redis"
                )
        return self._redis

    def _session_key(self, session_id: str) -> str:
        """生成 Session 存储键"""
        return f"session:{session_id}"

    def _pending_key(self, session_id: str) -> str:
        """生成 Pending Chats 存储键"""
        return f"session:{session_id}:pending"

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取 Session 状态

        Args:
            session_id: 会话 ID

        Returns:
            SessionState 或 None
        """
        key = self._session_key(session_id)

        try:
            data = await self.redis.hgetall(key)

            if not data:
                return None

            # 解析 Session 数据
            state = SessionState(
                session_id=session_id,
                user_id=data.get(b"user_id", b"").decode("utf-8") or None,
                user_name=data.get(b"user_name", b"").decode("utf-8") or None,
                chat_count=int(data.get(b"chat_count", 0)),
                identification_attempts=int(data.get(b"identification_attempts", 0)),
                is_identified=data.get(b"is_identified", b"false").decode("utf-8") == "true",
            )

            # 解析时间字段
            created_at_str = data.get(b"created_at")
            if created_at_str:
                state.created_at = datetime.fromisoformat(created_at_str.decode("utf-8"))

            last_active_at_str = data.get(b"last_active_at")
            if last_active_at_str:
                state.last_active_at = datetime.fromisoformat(last_active_at_str.decode("utf-8"))

            # 获取 pending_chats
            pending = await self._get_pending_chats(session_id)
            state.pending_chats = pending

            return state

        except Exception as e:
            logger.error(f"获取 Session 失败: {e}")
            return None

    async def _get_pending_chats(self, session_id: str) -> List[PendingChat]:
        """获取待存储的对话列表"""
        key = self._pending_key(session_id)

        try:
            chats_data = await self.redis.lrange(key, 0, -1)

            chats = []
            for chat_json in chats_data:
                chat_dict = json.loads(chat_json)
                chats.append(PendingChat(
                    user_input=chat_dict["user_input"],
                    assistant_response=chat_dict["assistant_response"],
                    timestamp=datetime.fromisoformat(chat_dict["timestamp"]),
                ))

            return chats

        except Exception as e:
            logger.error(f"获取 Pending Chats 失败: {e}")
            return []

    async def save_session(self, state: SessionState, ttl: int = 3600) -> bool:
        """保存 Session 状态

        Args:
            state: Session 状态
            ttl: 过期时间（秒）

        Returns:
            是否保存成功
        """
        key = self._session_key(session_id=state.session_id)

        try:
            # 保存 Session 字段
            data = {
                "user_id": state.user_id or "",
                "user_name": state.user_name or "",
                "chat_count": state.chat_count,
                "identification_attempts": state.identification_attempts,
                "is_identified": "true" if state.is_identified else "false",
                "created_at": state.created_at.isoformat(),
                "last_active_at": state.last_active_at.isoformat(),
            }

            await self.redis.hset(key, mapping={k: v for k, v in data.items() if isinstance(v, str)})
            await self.redis.hset(key, mapping={k: v for k, v in data.items() if isinstance(v, int)})
            await self.redis.expire(key, ttl)

            # 保存 pending_chats
            await self._save_pending_chats(state.session_id, state.pending_chats, ttl)

            return True

        except Exception as e:
            logger.error(f"保存 Session 失败: {e}")
            return False

    async def _save_pending_chats(
        self,
        session_id: str,
        chats: List[PendingChat],
        ttl: int,
    ) -> bool:
        """保存待存储的对话列表"""
        key = self._pending_key(session_id)

        try:
            # 删除旧数据
            await self.redis.delete(key)

            # 添加新数据
            if chats:
                chats_json = [
                    json.dumps({
                        "user_input": chat.user_input,
                        "assistant_response": chat.assistant_response,
                        "timestamp": chat.timestamp.isoformat(),
                    })
                    for chat in chats
                ]
                await self.redis.rpush(key, *chats_json)

            await self.redis.expire(key, ttl)
            return True

        except Exception as e:
            logger.error(f"保存 Pending Chats 失败: {e}")
            return False

    async def create_session(self, session_id: str) -> SessionState:
        """创建新 Session"""
        state = SessionState(session_id=session_id)
        await self.save_session(state)
        return state

    async def delete_session(self, session_id: str) -> bool:
        """删除 Session"""
        key = self._session_key(session_id)
        pending_key = self._pending_key(session_id)

        try:
            await self.redis.delete(key, pending_key)
            return True

        except Exception as e:
            logger.error(f"删除 Session 失败: {e}")
            return False

    async def touch_session(self, session_id: str) -> bool:
        """更新 Session 最后活跃时间"""
        key = self._session_key(session_id)

        try:
            await self.redis.hset(
                key,
                "last_active_at",
                datetime.now().isoformat(),
            )
            return True

        except Exception as e:
            logger.error(f"更新 Session 活跃时间失败: {e}")
            return False

    async def add_pending_chat(
        self,
        session_id: str,
        user_input: str,
        assistant_response: str,
    ) -> bool:
        """添加待存储的对话"""
        pending_key = self._pending_key(session_id)
        session_key = self._session_key(session_id)

        try:
            # 添加到列表
            chat_json = json.dumps({
                "user_input": user_input,
                "assistant_response": assistant_response,
                "timestamp": datetime.now().isoformat(),
            })
            await self.redis.rpush(pending_key, chat_json)

            # 更新计数和活跃时间
            await self.redis.hincrby(session_key, "chat_count", 1)
            await self.redis.hset(
                session_key,
                "last_active_at",
                datetime.now().isoformat(),
            )

            return True

        except Exception as e:
            logger.error(f"添加 Pending Chat 失败: {e}")
            return False

    async def clear_pending_chats(self, session_id: str) -> List[PendingChat]:
        """清空并返回待存储的对话"""
        chats = await self._get_pending_chats(session_id)

        pending_key = self._pending_key(session_id)
        session_key = self._session_key(session_id)

        try:
            await self.redis.delete(pending_key)
            await self.redis.hset(session_key, "chat_count", 0)

        except Exception as e:
            logger.error(f"清空 Pending Chats 失败: {e}")

        return chats

    async def set_user(
        self,
        session_id: str,
        user_id: str,
        user_name: str,
    ) -> bool:
        """设置 Session 的用户身份"""
        key = self._session_key(session_id)

        try:
            await self.redis.hset(key, mapping={
                "user_id": user_id,
                "user_name": user_name,
                "is_identified": "true",
            })
            return True

        except Exception as e:
            logger.error(f"设置用户身份失败: {e}")
            return False

    async def get_expired_sessions(
        self,
        timeout_minutes: int = 30,
    ) -> List[str]:
        """获取过期的 Session ID 列表

        注意：Redis 使用 TTL 自动过期，此方法主要用于手动检查
        """
        # 由于 Redis 使用 TTL 自动过期，这里返回空列表
        # 如果需要手动检查，可以扫描所有 session 键并检查 last_active_at
        return []

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
