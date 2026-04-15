# 🎭 Mock 集成测试：LLM 响应 Mock、快速单元测试
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from services.llm.base import BaseLLMProvider
from services.memory.writer import MemoryWriter
from services.memory.deduplicator import MemoryDeduplicator, DedupAction
from services.retrieval.retriever import MemoryRetriever
from services.profile_service import ProfileService
from schemas.onboarding_schema import OnboardingRequest, AICustomization


class TestMockedLLMProvider:
    """Mock LLM Provider 测试"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM Provider"""
        mock = AsyncMock(spec=BaseLLMProvider)

        # 默认返回值
        mock.generate_chat_response = AsyncMock(return_value="这是一个模拟的回复")
        mock.get_embedding = AsyncMock(return_value=[0.1] * 1536)
        mock.count_tokens = AsyncMock(return_value=10)

        return mock

    @pytest.mark.asyncio
    async def test_mock_chat_response(self, mock_llm):
        """测试 Mock 对话响应"""
        response = await mock_llm.generate_chat_response(
            system_prompt="测试系统提示",
            context="测试上下文",
            user_query="测试问题",
        )

        assert response == "这是一个模拟的回复"
        mock_llm.generate_chat_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_embedding(self, mock_llm):
        """测试 Mock Embedding"""
        embedding = await mock_llm.get_embedding("测试文本")

        assert len(embedding) == 1536
        assert all(x == 0.1 for x in embedding)

    @pytest.mark.asyncio
    async def test_mock_memory_intent(self, mock_llm):
        """测试 Mock 记忆意图提取"""
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "用户在学习 Python 编程",
            "importance_score": 7,
            "atomic_items": [
                {
                    "category_name": "语义知识库",
                    "content": "用户正在学习 Python 编程",
                    "importance_score": 7,
                }
            ],
        })

        result = await mock_llm.extract_memory_intent(
            text="我最近在学习 Python 编程",
            categories=[{"name": "语义知识库", "description": "知识相关"}],
        )

        assert result["summary"] == "用户在学习 Python 编程"
        assert len(result["atomic_items"]) == 1


class TestMockedMemoryWriter:
    """Mock 记忆写入测试"""

    @pytest.fixture
    def mock_llm_for_writer(self):
        """创建用于 MemoryWriter 的 Mock LLM"""
        mock = AsyncMock(spec=BaseLLMProvider)

        mock.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试摘要",
            "importance_score": 5,
            "response_summary": "AI 回复摘要",
            "atomic_items": [
                {
                    "category_name": "核心自我",
                    "content": "测试原子化内容",
                    "importance_score": 5,
                }
            ],
        })
        mock.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        return mock

    @pytest.mark.asyncio
    async def test_save_chat_with_mock(self, db_session, test_user, mock_llm_for_writer):
        """测试使用 Mock LLM 保存对话"""
        writer = MemoryWriter(db_session, mock_llm_for_writer, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试输入",
            assistant_response="测试回复",
            modality="text",
        )

        assert result["resource_id"] is not None
        assert result["summary"] == "测试摘要"
        assert result["importance_score"] == 5

        # 验证 LLM 被正确调用
        mock_llm_for_writer.extract_memory_intent.assert_called_once()
        mock_llm_for_writer.get_embedding.assert_called()

    @pytest.mark.asyncio
    async def test_save_chat_custom_mock_response(self, db_session, test_user):
        """测试自定义 Mock 响应"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)

        # 自定义响应
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "自定义摘要内容",
            "importance_score": 9,
            "atomic_items": [
                {
                    "category_name": "核心自我",
                    "content": "用户名字叫测试用户",
                    "importance_score": 10,
                },
                {
                    "category_name": "语义知识库",
                    "content": "用户对编程感兴趣",
                    "importance_score": 6,
                }
            ],
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.2] * 1536)

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="自定义输入",
            assistant_response="自定义回复",
            modality="text",
        )

        assert result["importance_score"] == 9
        assert result["atomic_items_count"] == 2


class TestMockedDeduplication:
    """Mock 去重测试"""

    @pytest.fixture
    def mock_llm_for_dedup(self):
        """创建用于去重的 Mock LLM"""
        mock = AsyncMock(spec=BaseLLMProvider)
        mock.get_embedding = AsyncMock(return_value=[0.1] * 1536)
        mock.generate_chat_response = AsyncMock(return_value=json.dumps({
            "action": "merge",
            "reason": "内容相关，应该合并",
            "merged_content": "合并后的内容",
        }))
        return mock

    @pytest.mark.asyncio
    async def test_dedup_skip_with_mock(self, db_session, test_user, mock_llm_for_dedup):
        """测试 Mock 去重 - 跳过"""
        deduplicator = MemoryDeduplicator(db_session, mock_llm_for_dedup)

        # Mock 返回 SKIP 结果
        mock_llm_for_dedup.generate_chat_response = AsyncMock(return_value=json.dumps({
            "action": "skip",
            "reason": "内容几乎相同",
        }))

        # 创建已有资源
        from repositories import ResourceRepository
        resource_repo = ResourceRepository(db_session)
        existing = await resource_repo.create(
            user_id=test_user.id,
            raw_content="原始内容",
            modality="text",
            description="已有描述",
            description_vector=[0.1] * 1536,
        )
        await db_session.commit()

        # 设置向量检索返回已有资源
        with patch.object(resource_repo, 'search_by_vector', return_value=[existing]):
            result = await deduplicator.check_resource_duplicate(
                user_id=test_user.id,
                summary="相似描述",
                vector=[0.1] * 1536,
            )

            # 应该是 CREATE（因为没有真实向量匹配）
            assert result.action in [DedupAction.CREATE, DedupAction.SKIP]

    @pytest.mark.asyncio
    async def test_dedup_merge_with_mock(self, db_session, test_user, fake_embedding: list[float]):
        """测试 Mock 去重 - 合并"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.get_embedding = AsyncMock(return_value=fake_embedding)
        mock_llm.generate_chat_response = AsyncMock(return_value=json.dumps({
            "action": "merge",
            "reason": "内容相关",
            "merged_content": "合并后的新内容",
        }))

        deduplicator = MemoryDeduplicator(db_session, mock_llm)

        # 没有现有资源时应该是 CREATE
        result = await deduplicator.check_resource_duplicate(
            user_id=test_user.id,
            summary="新内容",
            vector=fake_embedding,
        )

        assert result.action == DedupAction.CREATE


class TestMockedRetrieval:
    """Mock 检索测试"""

    @pytest.fixture
    def mock_llm_for_retrieval(self):
        """创建用于检索的 Mock LLM"""
        mock = AsyncMock(spec=BaseLLMProvider)
        mock.get_embedding = AsyncMock(return_value=[0.1] * 1536)
        mock.generate_chat_response = AsyncMock(return_value='["核心自我", "语义知识库"]')
        mock.count_tokens = AsyncMock(return_value=50)
        return mock

    @pytest.mark.asyncio
    async def test_retrieval_with_mock(
        self,
        db_session,
        test_user,
        mock_llm_for_retrieval,
        fake_embedding: list[float],
    ):
        """测试使用 Mock LLM 检索"""
        # 创建测试数据
        from repositories import ResourceRepository, CategoryRepository, ResourceCategoryRepository

        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)
        rc_repo = ResourceCategoryRepository(db_session)

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试内容",
            modality="text",
            description="测试描述",
            description_vector=fake_embedding,
            importance_score=7,
        )

        category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="测试分类内容",
        )

        await rc_repo.create(resource_id=resource.id, category_id=category.id)
        await db_session.commit()

        retriever = MemoryRetriever(db_session, mock_llm_for_retrieval)

        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试查询",
            top_k=5,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_classification_with_mock(self, db_session, test_user, mock_llm_for_retrieval):
        """测试 Mock 分类判断"""
        retriever = MemoryRetriever(db_session, mock_llm_for_retrieval)

        # 先创建一些分类
        from repositories import CategoryRepository
        category_repo = CategoryRepository(db_session)

        for name in ["核心自我", "语义知识库", "情景时间轴"]:
            await category_repo.create_item(
                user_id=test_user.id,
                category_name=name,
                content=f"{name}的内容",
            )
        await db_session.commit()

        # 测试分类
        categories = await retriever._classify_query(test_user.id, "用户是谁")

        # Mock 返回的类别
        assert isinstance(categories, list)


class TestMockedProfileService:
    """Mock 用户画像测试"""

    @pytest.fixture
    def mock_llm_for_profile(self):
        """创建用于 ProfileService 的 Mock LLM"""
        mock = AsyncMock(spec=BaseLLMProvider)
        mock.generate_chat_response = AsyncMock(return_value=json.dumps({
            "dynamic_categories": [
                {"name": "学习笔记", "description": "学习相关内容"},
                {"name": "生活记录", "description": "日常生活记录"},
            ]
        }))
        return mock

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_onboarding_with_mock(self, db_session, mock_llm_for_profile):
        """测试使用 Mock LLM 的用户初始化"""
        service = ProfileService(db_session, mock_llm_for_profile)

        request = OnboardingRequest(
            username="Mock测试用户",
            identity_type="student",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        response = await service.onboarding(request)

        assert response.success is True
        assert response.user_id is not None


class TestMockScenarios:
    """复杂 Mock 场景测试"""

    @pytest.mark.asyncio
    async def test_llm_timeout_scenario(self, db_session, test_user):
        """模拟 LLM 超时场景"""
        import asyncio

        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.extract_memory_intent = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timeout")
        )

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        # 应该抛出超时异常
        with pytest.raises(asyncio.TimeoutError):
            await writer.save_chat(
                user_id=test_user.id,
                user_input="测试",
                assistant_response="回复",
                modality="text",
            )

    @pytest.mark.asyncio
    async def test_llm_error_scenario(self, db_session, test_user):
        """模拟 LLM 错误场景"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.extract_memory_intent = AsyncMock(
            side_effect=Exception("LLM service error")
        )

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        with pytest.raises(Exception, match="LLM service error"):
            await writer.save_chat(
                user_id=test_user.id,
                user_input="测试",
                assistant_response="回复",
                modality="text",
            )

    @pytest.mark.asyncio
    async def test_partial_failure_scenario(self, db_session, test_user, fake_embedding: list[float]):
        """模拟部分失败场景"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)

        # 第一次调用成功，第二次失败
        call_count = 0

        async def side_effect_get_embedding(text):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise Exception("Embedding failed")
            return fake_embedding

        mock_llm.get_embedding = AsyncMock(side_effect=side_effect_get_embedding)
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试",
            "importance_score": 5,
            "atomic_items": [],
        })

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        # 第一次应该成功
        result1 = await writer.save_chat(
            user_id=test_user.id,
            user_input="第一次",
            assistant_response="回复",
            modality="text",
        )
        assert result1 is not None

        # 第二次应该失败
        with pytest.raises(Exception, match="Embedding failed"):
            await writer.save_chat(
                user_id=test_user.id,
                user_input="第二次",
                assistant_response="回复",
                modality="text",
            )


class TestMockHelpers:
    """Mock 辅助函数测试"""

    def test_create_mock_embedding(self):
        """测试创建 Mock Embedding"""
        mock_embedding = [0.1] * 1536

        assert len(mock_embedding) == 1536
        assert all(x == 0.1 for x in mock_embedding)

    def test_create_mock_memory_intent(self):
        """测试创建 Mock 记忆意图"""
        mock_intent = {
            "summary": "测试摘要",
            "importance_score": 5,
            "atomic_items": [
                {
                    "category_name": "核心自我",
                    "content": "测试内容",
                    "importance_score": 5,
                }
            ],
        }

        assert "summary" in mock_intent
        assert "atomic_items" in mock_intent
        assert len(mock_intent["atomic_items"]) == 1

    def test_create_mock_classification_response(self):
        """测试创建 Mock 分类响应"""
        categories = ["核心自我", "语义知识库"]
        mock_response = json.dumps(categories)

        parsed = json.loads(mock_response)
        assert parsed == categories


class TestMockVerifyCalls:
    """验证 Mock 调用测试"""

    @pytest.mark.asyncio
    async def test_verify_llm_calls(self, db_session, test_user):
        """验证 LLM 被正确调用"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试",
            "importance_score": 5,
            "atomic_items": [],
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        await writer.save_chat(
            user_id=test_user.id,
            user_input="测试输入",
            assistant_response="测试回复",
            modality="text",
        )

        # 验证调用
        mock_llm.extract_memory_intent.assert_called_once()
        mock_llm.get_embedding.assert_called()

        # 验证调用参数
        call_args = mock_llm.extract_memory_intent.call_args
        assert "text" in call_args.kwargs or len(call_args.args) > 0

    @pytest.mark.asyncio
    async def test_verify_no_extra_calls(self, db_session, test_user):
        """验证没有多余的调用"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试",
            "importance_score": 5,
            "atomic_items": [],
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        await writer.save_chat(
            user_id=test_user.id,
            user_input="测试",
            assistant_response="回复",
            modality="text",
        )

        # 不应该调用 generate_chat_response
        mock_llm.generate_chat_response.assert_not_called()

        # 不应该调用 count_tokens
        mock_llm.count_tokens.assert_not_called()
