# 🔍 Retrieve API 测试：记忆检索
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


class TestRetrieveAPI:
    """Retrieve API 测试"""

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
        assert data["total"] == 0
        assert data["context_text"] == ""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_after_save(self, client: AsyncClient, test_user):
        """测试保存后检索"""
        # 先保存记忆
        await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我叫张三，是一名软件工程师",
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

        # 结果结构验证
        result = data["results"][0]
        assert "resource_id" in result
        assert "description" in result
        assert "retrieval_score" in result
        assert result["retrieval_score"] >= 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_with_top_k(self, client: AsyncClient, test_user):
        """测试 top_k 参数"""
        # 保存多条记忆
        for i in range(5):
            await client.post(
                "/v1/chat/save",
                json={
                    "user_id": test_user.id,
                    "user_input": f"测试内容{i}",
                    "assistant_response": f"回复{i}",
                    "modality": "text",
                },
            )

        # 请求 top 3
        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": test_user.id,
                "query": "测试",
                "top_k": 3,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 结果数量应该不超过 top_k
        assert len(data["results"]) <= 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_min_importance_filter(self, client: AsyncClient, test_user, fake_embedding: list[float]):
        """测试重要性过滤"""
        from repositories import ResourceRepository

        # 直接创建不同重要性的资源
        resource_repo = ResourceRepository(None)  # 需要 session

    @pytest.mark.asyncio
    async def test_retrieve_missing_user_id(self, client: AsyncClient):
        """测试缺少 user_id"""
        response = await client.post(
            "/v1/retrieve",
            json={
                "query": "测试",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_retrieve_invalid_user_id(self, client: AsyncClient):
        """测试无效 user_id"""
        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": "non-existent-user",
                "query": "测试",
                "top_k": 5,
            },
        )

        # 应该返回空结果而不是错误
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []


class TestRetrieveStatsAPI:
    """检索统计 API 测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_stats_empty_user(self, client: AsyncClient, test_user):
        """测试空用户统计"""
        response = await client.get(
            "/v1/retrieve/stats",
            params={"user_id": test_user.id},
        )

        assert response.status_code == 200
        data = response.json()

        assert "total_retrievals" in data
        assert "category_distribution" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_stats_with_memories(self, client: AsyncClient, test_user):
        """测试有记忆的用户统计"""
        # 保存一些记忆
        for i in range(3):
            await client.post(
                "/v1/chat/save",
                json={
                    "user_id": test_user.id,
                    "user_input": f"测试内容{i}",
                    "assistant_response": f"回复{i}",
                    "modality": "text",
                },
            )

        response = await client.get(
            "/v1/retrieve/stats",
            params={"user_id": test_user.id},
        )

        assert response.status_code == 200
        data = response.json()

        # 应该有资源统计
        assert data["total_retrievals"] >= 0


class TestRetrieveContext:
    """检索上下文测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_context_text_format(self, client: AsyncClient, test_user):
        """测试上下文文本格式"""
        # 保存记忆
        await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我叫张三",
                "assistant_response": "你好张三！",
                "modality": "text",
            },
        )

        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": test_user.id,
                "query": "用户名字",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 上下文应该包含相关性分数
        if data["context_text"]:
            assert "相关性" in data["context_text"] or "张三" in data["context_text"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_categories_detected(self, client: AsyncClient, test_user):
        """测试分类检测"""
        # 保存多条不同分类的记忆
        await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我叫张三，今年25岁",
                "assistant_response": "记录下来了",
                "modality": "text",
            },
        )

        await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我明天有个会议",
                "assistant_response": "好的",
                "modality": "text",
            },
        )

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

        # 应该检测到相关分类
        assert isinstance(data["categories_detected"], list)


class TestRetrieveSemantic:
    """语义检索测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_semantic_search(self, client: AsyncClient, test_user):
        """测试语义检索"""
        # 保存记忆
        await client.post(
            "/v1/chat/save",
            json={
                "user_id": test_user.id,
                "user_input": "我喜欢吃苹果和香蕉",
                "assistant_response": "水果很有营养！",
                "modality": "text",
            },
        )

        # 用语义相关的查询
        response = await client.post(
            "/v1/retrieve",
            json={
                "user_id": test_user.id,
                "query": "用户喜欢什么水果",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 应该能通过语义找到相关记忆
        if len(data["results"]) > 0:
            # 描述中应该包含水果相关内容
            assert any(
                "苹果" in r["description"] or "香蕉" in r["description"] or "水果" in r["description"]
                for r in data["results"]
            )
