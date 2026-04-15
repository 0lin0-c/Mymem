# 💾 Memory API 测试：记忆保存、查询
import pytest
import pytest_asyncio
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


class TestSaveMemoryAPI:
    """保存记忆 API 测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_memory_success(self, client: AsyncClient, test_user):
        """测试成功保存记忆"""
        response = await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我今天学习了 Python 的异步编程",
                "assistant_response": "异步编程是 Python 的重要特性！",
                "modality": "text",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["resource_id"] is not None
        assert "message" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_memory_with_different_modalities(self, client: AsyncClient, test_user):
        """测试不同模态保存"""
        modalities = ["text", "image", "voice"]

        for modality in modalities:
            response = await client.post(
                "/v1/chat/save",
                json={
                    "user_id": test_user.id,
                    "user_input": f"{modality} 内容",
                    "assistant_response": f"{modality} 回复",
                    "modality": modality,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_save_memory_user_not_found(self, client: AsyncClient):
        """测试用户不存在"""
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

    @pytest.mark.asyncio
    async def test_save_memory_missing_fields(self, client: AsyncClient):
        """测试缺少必填字段"""
        response = await client.post(
            "/v1/chat/save",
            json={
                "user_id": "some-user",
                # 缺少 user_input 和 assistant_response
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_memory_long_content(self, client: AsyncClient, test_user):
        """测试长内容保存"""
        long_content = "这是一段很长的内容。" * 1000

        response = await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": long_content,
                "assistant_response": "收到",
                "modality": "text",
            },
        )

        # 应该能正常处理
        assert response.status_code == 200


class TestMemoryAPIIntegration:
    """Memory API 集成测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_and_retrieve_flow(self, client: AsyncClient, test_user):
        """测试保存后检索的完整流程"""
        # 1. 保存多条记忆
        memories = [
            ("我叫张三", "你好张三！"),
            ("我今年25岁", "记录下来了"),
            ("我喜欢编程", "编程是很有趣的！"),
        ]

        for user_input, assistant_response in memories:
            await client.post(
                "/v1/chat/save",
                json={
                    "user_id": test_user.id,
                    "user_input": user_input,
                    "assistant_response": assistant_response,
                    "modality": "text",
                },
            )

        # 2. 检索相关记忆
        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": test_user.id,
                "query": "用户的身份信息",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 应该能找到相关记忆
        assert len(data["results"]) >= 1

        # 检索结果应该包含上下文
        assert "context_text" in data


class TestChatBatchSave:
    """对话批量保存测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_accumulation(self, client: AsyncClient):
        """测试对话累积（达到阈值才保存）"""
        session_id = "test_batch_session"

        # 发送多轮对话
        for i in range(3):
            response = await client.post(
                "/v1/chat",
                json={
                    "session_id": session_id,
                    "query": f"这是第{i+1}轮对话",
                    "modality": "text",
                },
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_flush_keyword(self, client: AsyncClient):
        """测试关键词触发立即落库"""
        session_id = "test_flush_session"

        # 先发送几轮对话
        for i in range(2):
            await client.post(
                "/v1/chat",
                json={
                    "session_id": session_id,
                    "query": f"对话{i+1}",
                    "modality": "text",
                },
            )

        # 发送触发关键词
        response = await client.post(
            "/v1/chat",
            json={
                "session_id": session_id,
                "query": "再见，下次见",
                "modality": "text",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # "再见" 应该触发 flush
        assert data.get("flushed") is True
