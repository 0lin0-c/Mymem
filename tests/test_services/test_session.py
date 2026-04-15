# 🔧 Session 管理测试：会话状态、用户识别、过期清理
import pytest
from datetime import datetime, timedelta

from services.session.session_manager import SessionManager, FlushableSession
from services.session.state import SessionState, PendingChat
from services.session.user_identifier import UserIdentifier


class TestSessionState:
    """SessionState 测试"""

    def test_session_state_creation(self):
        """测试会话状态创建"""
        state = SessionState(session_id="test_session_001")

        assert state.session_id == "test_session_001"
        assert state.user_id is None
        assert state.user_name is None
        assert state.is_identified is False
        assert state.chat_count == 0
        assert len(state.pending_chats) == 0

    def test_session_state_touch(self):
        """测试会话活跃时间更新"""
        state = SessionState(session_id="test")
        old_time = state.last_active_at

        # 等待一小段时间
        import time
        time.sleep(0.01)

        state.touch()

        assert state.last_active_at > old_time

    def test_add_pending_chat(self):
        """测试添加待存储对话"""
        state = SessionState(session_id="test")

        state.pending_chats.append(PendingChat(
            user_input="你好",
            assistant_response="你好！有什么可以帮你的？",
        ))
        state.chat_count += 1

        assert len(state.pending_chats) == 1
        assert state.chat_count == 1


class TestSessionManager:
    """SessionManager 测试"""

    def test_create_session(self):
        """测试创建会话"""
        manager = SessionManager()
        state = manager.create_session("session_001")

        assert state.session_id == "session_001"
        assert manager.get_session("session_001") == state

    def test_get_session_not_exists(self):
        """测试获取不存在的会话"""
        manager = SessionManager()
        state = manager.get_session("non_existent")

        assert state is None

    def test_get_or_create(self):
        """测试获取或创建会话"""
        manager = SessionManager()

        # 第一次创建
        state1 = manager.get_or_create("session_001")
        assert state1.session_id == "session_001"

        # 第二次获取已存在的
        state2 = manager.get_or_create("session_001")
        assert state2 == state1

    def test_destroy_session(self):
        """测试销毁会话"""
        manager = SessionManager()
        manager.create_session("session_001")

        destroyed = manager.destroy_session("session_001")
        assert destroyed is True
        assert manager.get_session("session_001") is None

    def test_destroy_session_not_exists(self):
        """测试销毁不存在的会话"""
        manager = SessionManager()
        destroyed = manager.destroy_session("non_existent")
        assert destroyed is False

    def test_add_pending_chat(self):
        """测试添加待存储对话"""
        manager = SessionManager()

        state = manager.add_pending_chat(
            session_id="session_001",
            user_input="用户问题",
            assistant_response="助手回答",
        )

        assert len(state.pending_chats) == 1
        assert state.chat_count == 1
        assert state.pending_chats[0].user_input == "用户问题"

    def test_clear_pending_chats(self):
        """测试清空待存储对话"""
        manager = SessionManager()

        manager.add_pending_chat("session_001", "问题1", "回答1")
        manager.add_pending_chat("session_001", "问题2", "回答2")

        chats = manager.clear_pending_chats("session_001")

        assert len(chats) == 2
        state = manager.get_session("session_001")
        assert len(state.pending_chats) == 0
        assert state.chat_count == 0

    def test_set_user(self):
        """测试设置用户身份"""
        manager = SessionManager()

        state = manager.set_user(
            session_id="session_001",
            user_id="user_123",
            user_name="张三",
        )

        assert state.user_id == "user_123"
        assert state.user_name == "张三"
        assert state.is_identified is True

    def test_cleanup_expired(self):
        """测试清理过期会话"""
        manager = SessionManager(session_timeout_minutes=30)

        # 创建会话并设置过期时间
        state = manager.create_session("old_session")
        state.last_active_at = datetime.now() - timedelta(minutes=60)

        manager.create_session("new_session")

        # 清理过期
        cleaned = manager.cleanup_expired()

        assert cleaned == 1
        assert manager.get_session("old_session") is None
        assert manager.get_session("new_session") is not None

    def test_get_expired_sessions_with_pending(self):
        """测试获取过期且有待存储对话的会话"""
        manager = SessionManager(session_timeout_minutes=30)

        # 创建过期的已识别会话，有待存储对话
        state = manager.create_session("expired_with_pending")
        state.user_id = "user_123"
        state.user_name = "张三"
        state.is_identified = True
        state.pending_chats.append(PendingChat(
            user_input="问题",
            assistant_response="回答",
        ))
        state.last_active_at = datetime.now() - timedelta(minutes=60)

        # 创建过期的未识别会话
        state2 = manager.create_session("expired_unidentified")
        state2.last_active_at = datetime.now() - timedelta(minutes=60)

        flushable = manager.get_expired_sessions_with_pending()

        assert len(flushable) == 1
        assert flushable[0].session_id == "expired_with_pending"
        assert flushable[0].user_id == "user_123"
        assert len(flushable[0].pending_chats) == 1

    def test_mark_flushed(self):
        """测试标记已落库"""
        manager = SessionManager()

        manager.add_pending_chat("session_001", "问题", "回答")
        manager.mark_flushed("session_001")

        state = manager.get_session("session_001")
        assert len(state.pending_chats) == 0

    def test_get_and_clear_pending(self):
        """测试原子获取并清除待存储对话"""
        manager = SessionManager()

        manager.add_pending_chat("session_001", "问题1", "回答1")
        manager.set_user("session_001", "user_123", "张三")

        chats, user_id, user_name = manager.get_and_clear_pending("session_001")

        assert len(chats) == 1
        assert user_id == "user_123"
        assert user_name == "张三"

        state = manager.get_session("session_001")
        assert len(state.pending_chats) == 0


class TestUserIdentifier:
    """UserIdentifier 用户识别测试"""

    @pytest.mark.asyncio
    async def test_identify_already_identified(self, db_session, llm_provider):
        """测试已识别用户直接返回"""
        identifier = UserIdentifier(llm_provider, db_session)

        state = SessionState(session_id="test")
        state.is_identified = True
        state.user_id = "user_123"
        state.user_name = "张三"

        result = await identifier.identify_or_ask(state, "任何输入")

        assert result["identified"] is True
        assert result["user_id"] == "user_123"
        assert result["response"] is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_identify_new_user(self, db_session, llm_provider):
        """测试识别新用户"""
        identifier = UserIdentifier(llm_provider, db_session)

        state = SessionState(session_id="test_new_user")

        result = await identifier.identify_or_ask(
            state,
            "我叫李四，是新用户",
        )

        # LLM 应该识别出用户名
        if result["identified"]:
            assert result["user_name"] == "李四"
        else:
            # 可能需要继续询问
            assert result["response"] is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_identify_existing_user(self, db_session, test_user, llm_provider):
        """测试识别已有用户"""
        identifier = UserIdentifier(llm_provider, db_session)

        state = SessionState(session_id="test_existing")

        result = await identifier.identify_or_ask(
            state,
            f"我是{test_user.username}",
        )

        # 应该识别到已有用户并请求验证
        if not result["identified"]:
            assert result["requires_verification"] is True

    @pytest.mark.asyncio
    async def test_identify_max_attempts(self, db_session, llm_provider):
        """测试超过最大询问次数创建临时用户"""
        identifier = UserIdentifier(llm_provider, db_session)

        state = SessionState(session_id="test_max_attempts")
        state.identification_attempts = identifier.MAX_IDENTIFICATION_ATTEMPTS

        result = await identifier.identify_or_ask(state, "随便说点什么")

        # 超过最大次数，应该创建临时用户
        assert result["identified"] is True
        assert result["user_id"] is not None
        assert "临时" in result["response"] or "guest" in result["user_name"]

    def test_fallback_parse(self, db_session, llm_provider):
        """测试降级关键词解析"""
        identifier = UserIdentifier(llm_provider, db_session)

        # 测试各种身份声明格式
        test_cases = [
            ("我是张三", "张三"),
            ("我叫李四", "李四"),
            ("名字是小明", "小明"),
            ("叫我大王", "大王"),
        ]

        for input_text, expected_name in test_cases:
            result = identifier._fallback_parse(input_text)
            assert result["action"] == "identified"
            assert result["user_name"] == expected_name

    def test_fallback_parse_no_identity(self, db_session, llm_provider):
        """测试降级解析无法识别身份"""
        identifier = UserIdentifier(llm_provider, db_session)

        result = identifier._fallback_parse("今天天气怎么样？")

        assert result["action"] == "ask"
        assert result["response"] is not None


class TestPendingChat:
    """PendingChat 数据类测试"""

    def test_pending_chat_creation(self):
        """测试创建待存储对话"""
        chat = PendingChat(
            user_input="用户问题",
            assistant_response="助手回答",
        )

        assert chat.user_input == "用户问题"
        assert chat.assistant_response == "助手回答"
        assert chat.timestamp is not None


class TestFlushableSession:
    """FlushableSession 数据类测试"""

    def test_flushable_session_creation(self):
        """测试创建可落库会话数据"""
        chats = [PendingChat(user_input="Q", assistant_response="A")]
        flushable = FlushableSession(
            session_id="session_001",
            user_id="user_123",
            user_name="张三",
            pending_chats=chats,
        )

        assert flushable.session_id == "session_001"
        assert flushable.user_id == "user_123"
        assert len(flushable.pending_chats) == 1
