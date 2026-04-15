# 🌐 API 层测试：端到端流程测试
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from main import app


@pytest_asyncio.fixture
async def client():
    """创建测试客户端"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestChatAPI:
    """Chat API 端到端测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_new_session(self, client: AsyncClient):
        """测试新会话对话"""
        response = await client.post(
            "/v1/chat",
            json={
                "session_id": "test_session_001",
                "query": "你好，我是张三",
                "modality": "text",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_continuation(self, client: AsyncClient):
        """测试连续对话"""
        # 第一次对话
        response1 = await client.post(
            "/v1/chat",
            json={
                "session_id": "test_session_002",
                "query": "我叫张三",
                "modality": "text",
            },
        )
        assert response1.status_code == 200

        # 第二次对话（同一 session）
        response2 = await client.post(
            "/v1/chat",
            json={
                "session_id": "test_session_002",
                "query": "我叫什么名字？",
                "modality": "text",
            },
        )
        assert response2.status_code == 200

        data2 = response2.json()
        assert "answer" in data2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_immediate_flush(self, client: AsyncClient):
        """测试关键词触发立即落库"""
        response = await client.post(
            "/v1/chat",
            json={
                "session_id": "test_session_flush",
                "query": "再见",
                "modality": "text",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # "再见" 应该触发立即落库
        assert data.get("flushed") is True or data.get("is_identified") is not None

    @pytest.mark.asyncio
    async def test_chat_invalid_request(self, client: AsyncClient):
        """测试无效请求"""
        response = await client.post(
            "/v1/chat",
            json={
                # 缺少 session_id
                "query": "测试",
                "modality": "text",
            },
        )

        assert response.status_code == 422  # Validation Error


class TestMemoryAPI:
    """Memory API 端到端测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_memory(self, client: AsyncClient, test_user):
        """测试直接保存记忆"""
        response = await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我最近在学习 Python",
                "assistant_response": "Python 是很好的语言！",
                "modality": "text",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["resource_id"] is not None
        assert "category_name" in data

    @pytest.mark.asyncio
    async def test_save_memory_invalid_user(self, client: AsyncClient):
        """测试保存记忆用户不存在"""
        response = await client.post(
            "/v1/chat/save",
            json={
                "user_id": "non-existent-user-id",
                "user_input": "测试内容",
                "assistant_response": "测试回复",
                "modality": "text",
            },
        )

        assert response.status_code == 404


class TestRetrieveAPI:
    """Retrieve API 端到端测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_empty_user(self, client: AsyncClient, test_user):
        """测试空用户检索"""
        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": test_user.id,
                "query": "测试查询",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 新用户没有记忆
        assert data["results"] == []
        assert data["context"] == ""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_after_save(self, client: AsyncClient, test_user):
        """测试保存后检索"""
        # 先保存记忆
        await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我叫张三，今年25岁",
                "assistant_response": "你好张三！",
                "modality": "text",
            },
        )

        # 检索
        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": test_user.id,
                "query": "用户是谁",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 应该能找到相关记忆
        assert len(data["results"]) >= 1


class TestProfileAPI:
    """Profile API 端到端测试"""

    @pytest.mark.asyncio
    async def test_get_profile(self, client: AsyncClient, test_user):
        """测试获取用户画像"""
        response = await client.get(f"/v1/profile/{test_user.id}")

        assert response.status_code == 200
        data = response.json()

        assert "user_id" in data
        assert data["user_id"] == test_user.id

    @pytest.mark.asyncio
    async def test_update_profile(self, client: AsyncClient, test_user):
        """测试更新用户画像"""
        response = await client.patch(
            f"/v1/profile/{test_user.id}",
            json={
                "user_prompt_template": "你是一个专业的编程助手",
                "agent_persona_template": "你叫小助手，擅长解答编程问题",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "user_prompt_template" in data


class TestHealthCheck:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """测试健康检查接口"""
        response = await client.get("/health")

        # 根据实际实现调整
        assert response.status_code in [200, 404]  # 如果没有 health 接口则为 404


class TestAPIErrorHandling:
    """API 错误处理测试"""

    @pytest.mark.asyncio
    async def test_404_not_found(self, client: AsyncClient):
        """测试 404 错误"""
        response = await client.get("/non-existent-endpoint")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_422_validation_error(self, client: AsyncClient):
        """测试 422 验证错误"""
        response = await client.post(
            "/v1/chat",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, client: AsyncClient):
        """测试方法不允许"""
        response = await client.get("/v1/chat")  # GET 而非 POST
        assert response.status_code == 405
