# 🔄 Redis Session 存储测试：分布式会话管理
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.session.redis_store import RedisSessionStore
from services.session.state import SessionState, PendingChat


class TestRedisSessionStoreInit:
    """RedisSessionStore 初始化测试"""

    def test_init_with_url(self):
        """测试使用 URL 初始化"""
        store = RedisSessionStore(redis_url="redis://localhost:6379/0")
        assert store.redis_url == "redis://localhost:6379/0"

    def test_init_missing_url(self):
        """测试缺少 URL 时初始化失败"""
        with patch("core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            with pytest.raises(ValueError, match="Redis URL"):
                RedisSessionStore()


class TestRedisKeyGeneration:
    """Redis 键生成测试"""

    def test_session_key(self):
        """测试 Session 键生成"""
        store = RedisSessionStore.__new__(RedisSessionStore)
        key = store._session_key("test_session_123")
        assert key == "session:test_session_123"

    def test_pending_key(self):
        """测试 Pending Chats 键生成"""
        store = RedisSessionStore.__new__(RedisSessionStore)
        key = store._pending_key("test_session_123")
        assert key == "session:test_session_123:pending"


class TestRedisSessionStoreMocked:
    """使用 Mock 的 Redis 存储测试"""

    @pytest.fixture
    def mock_redis(self):
        """创建模拟 Redis 客户端"""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def store(self, mock_redis):
        """创建 RedisSessionStore 实例"""
        store = RedisSessionStore.__new__(RedisSessionStore)
        store.redis_url = "redis://localhost:6379/0"
        store._redis = mock_redis
        return store

    @pytest.mark.asyncio
    async def test_create_session(self, store, mock_redis):
        """测试创建 Session"""
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.delete = AsyncMock()

        state = await store.create_session("new_session_001")

        assert state.session_id == "new_session_001"
        assert state.user_id is None
        assert state.is_identified is False

    @pytest.mark.asyncio
    async def test_get_session(self, store, mock_redis):
        """测试获取 Session"""
        mock_redis.hgetall = AsyncMock(return_value={
            b"user_id": b"user_123",
            b"user_name": "张三".encode("utf-8"),
            b"chat_count": b"5",
            b"identification_attempts": b"0",
            b"is_identified": b"true",
            b"created_at": b"2024-01-01T00:00:00",
            b"last_active_at": b"2024-01-01T12:00:00",
        })
        mock_redis.lrange = AsyncMock(return_value=[])

        state = await store.get_session("existing_session")

        assert state is not None
        assert state.user_id == "user_123"
        assert state.user_name == "张三"
        assert state.chat_count == 5
        assert state.is_identified is True

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, store, mock_redis):
        """测试获取不存在的 Session"""
        mock_redis.hgetall = AsyncMock(return_value={})

        state = await store.get_session("nonexistent_session")

        assert state is None

    @pytest.mark.asyncio
    async def test_save_session(self, store, mock_redis):
        """测试保存 Session"""
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.rpush = AsyncMock()

        state = SessionState(session_id="test_session")
        state.user_id = "user_123"
        state.user_name = "张三"
        state.is_identified = True
        state.chat_count = 3

        success = await store.save_session(state, ttl=3600)

        assert success is True
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_delete_session(self, store, mock_redis):
        """测试删除 Session"""
        mock_redis.delete = AsyncMock()

        success = await store.delete_session("session_to_delete")

        assert success is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_pending_chat(self, store, mock_redis):
        """测试添加待存储对话"""
        mock_redis.rpush = AsyncMock()
        mock_redis.hincrby = AsyncMock()
        mock_redis.hset = AsyncMock()

        success = await store.add_pending_chat(
            session_id="test_session",
            user_input="用户问题",
            assistant_response="助手回答",
        )

        assert success is True
        mock_redis.rpush.assert_called_once()
        mock_redis.hincrby.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_pending_chats(self, store, mock_redis):
        """测试清空待存储对话"""
        mock_redis.lrange = AsyncMock(return_value=[
            b'{"user_input": "Q1", "assistant_response": "A1", "timestamp": "2024-01-01T00:00:00"}',
        ])
        mock_redis.delete = AsyncMock()
        mock_redis.hset = AsyncMock()

        chats = await store.clear_pending_chats("test_session")

        assert len(chats) == 1
        assert chats[0].user_input == "Q1"
        assert chats[0].assistant_response == "A1"

    @pytest.mark.asyncio
    async def test_set_user(self, store, mock_redis):
        """测试设置用户身份"""
        mock_redis.hset = AsyncMock()

        success = await store.set_user(
            session_id="test_session",
            user_id="user_123",
            user_name="张三",
        )

        assert success is True
        mock_redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_touch_session(self, store, mock_redis):
        """测试更新 Session 活跃时间"""
        mock_redis.hset = AsyncMock()

        success = await store.touch_session("test_session")

        assert success is True
        mock_redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_chats(self, store, mock_redis):
        """测试获取待存储对话"""
        mock_redis.lrange = AsyncMock(return_value=[
            b'{"user_input": "Q1", "assistant_response": "A1", "timestamp": "2024-01-01T00:00:00"}',
            b'{"user_input": "Q2", "assistant_response": "A2", "timestamp": "2024-01-01T00:01:00"}',
        ])

        chats = await store._get_pending_chats("test_session")

        assert len(chats) == 2
        assert chats[0].user_input == "Q1"
        assert chats[1].user_input == "Q2"

    @pytest.mark.asyncio
    async def test_get_expired_sessions(self, store, mock_redis):
        """测试获取过期 Session（Redis 使用 TTL）"""
        result = await store.get_expired_sessions()

        # Redis 使用 TTL 自动过期，返回空列表
        assert result == []


class TestRedisSessionStoreErrorHandling:
    """Redis 存储错误处理测试"""

    @pytest.fixture
    def store(self):
        """创建 RedisSessionStore 实例"""
        store = RedisSessionStore.__new__(RedisSessionStore)
        store.redis_url = "redis://localhost:6379/0"
        store._redis = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_get_session_error(self, store):
        """测试获取 Session 错误处理"""
        store._redis.hgetall = AsyncMock(side_effect=Exception("Redis error"))

        state = await store.get_session("test_session")

        assert state is None

    @pytest.mark.asyncio
    async def test_save_session_error(self, store):
        """测试保存 Session 错误处理"""
        store._redis.hset = AsyncMock(side_effect=Exception("Redis error"))
        store._redis.delete = AsyncMock()
        store._redis.rpush = AsyncMock()
        store._redis.expire = AsyncMock()

        state = SessionState(session_id="test")
        success = await store.save_session(state)

        assert success is False

    @pytest.mark.asyncio
    async def test_get_pending_chats_error(self, store):
        """测试获取 Pending Chats 错误处理"""
        store._redis.lrange = AsyncMock(side_effect=Exception("Redis error"))

        chats = await store._get_pending_chats("test_session")

        assert chats == []


class TestRedisPendingChatsSerialization:
    """Pending Chats 序列化测试"""

    def test_pending_chat_json_serialization(self):
        """测试 PendingChat JSON 序列化"""
        import json

        chat = PendingChat(
            user_input="问题",
            assistant_response="回答",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        json_str = json.dumps({
            "user_input": chat.user_input,
            "assistant_response": chat.assistant_response,
            "timestamp": chat.timestamp.isoformat(),
        })

        # 应该能正确序列化
        data = json.loads(json_str)
        assert data["user_input"] == "问题"
        assert data["assistant_response"] == "回答"

    def test_pending_chat_json_deserialization(self):
        """测试 PendingChat JSON 反序列化"""
        import json

        json_str = '{"user_input": "Q", "assistant_response": "A", "timestamp": "2024-01-01T12:00:00"}'
        data = json.loads(json_str)

        chat = PendingChat(
            user_input=data["user_input"],
            assistant_response=data["assistant_response"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )

        assert chat.user_input == "Q"
        assert chat.assistant_response == "A"


class TestRedisConnectionManagement:
    """Redis 连接管理测试"""

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """测试关闭连接"""
        store = RedisSessionStore.__new__(RedisSessionStore)
        store.redis_url = "redis://localhost:6379/0"
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        store._redis = mock_redis

        await store.close()

        mock_redis.close.assert_called_once()
        assert store._redis is None

    @pytest.mark.asyncio
    async def test_close_without_connection(self):
        """测试没有连接时关闭"""
        store = RedisSessionStore.__new__(RedisSessionStore)
        store.redis_url = "redis://localhost:6379/0"
        store._redis = None

        # 应该不会报错
        await store.close()


@pytest.mark.integration
class TestRedisSessionStoreIntegration:
    """Redis 存储集成测试（需要真实 Redis）"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 Redis 环境")
    async def test_real_redis_connection(self):
        """测试真实 Redis 连接"""
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 Redis 环境")
    async def test_real_session_round_trip(self):
        """测试真实 Session 完整流程"""
        pass
