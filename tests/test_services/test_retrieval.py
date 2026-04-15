# 🔎 记忆检索测试：LLM 分类 + 向量检索 + 分数计算
import pytest

from services.retrieval.retriever import MemoryRetriever, FOUR_FACTOR_THRESHOLD_LOW
from services.retrieval.vector_strategy import VectorStrategy


class TestMemoryRetriever:
    """MemoryRetriever 核心功能测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_empty_user(self, db_session, test_user, llm_provider):
        """测试空用户检索"""
        retriever = MemoryRetriever(db_session, llm_provider)

        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试查询",
            top_k=5,
        )

        # 新用户没有记忆
        assert len(results) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_after_save(self, db_session, test_user, llm_provider):
        """测试保存后检索"""
        from services.memory.writer import MemoryWriter

        # 先保存一条记忆
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)
        await writer.save_chat(
            user_id=test_user.id,
            user_input="我叫张三，是一名软件工程师",
            assistant_response="你好张三！",
            modality="text",
        )
        await db_session.commit()

        # 检索
        retriever = MemoryRetriever(db_session, llm_provider)
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="用户的名字是什么",
            top_k=5,
        )

        assert len(results) >= 1
        assert results[0]["resource"] is not None
        assert results[0]["score"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_with_llm_classification(self, db_session, test_user, llm_provider):
        """测试使用 LLM 分类的检索"""
        from services.memory.writer import MemoryWriter

        # 保存多条不同分类的记忆
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        await writer.save_chat(
            user_id=test_user.id,
            user_input="我叫张三",
            assistant_response="你好！",
            modality="text",
        )

        await writer.save_chat(
            user_id=test_user.id,
            user_input="我今天去公园散步了",
            assistant_response="很棒的体验！",
            modality="text",
        )

        await db_session.commit()

        # 检索
        retriever = MemoryRetriever(db_session, llm_provider)
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="用户是谁",
            top_k=5,
            use_llm_classification=True,
        )

        # 应该能找到相关记忆
        assert len(results) >= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_without_llm_classification(self, db_session, test_user, llm_provider):
        """测试不使用 LLM 分类的纯向量检索"""
        from services.memory.writer import MemoryWriter

        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)
        await writer.save_chat(
            user_id=test_user.id,
            user_input="我喜欢吃苹果",
            assistant_response="苹果很有营养！",
            modality="text",
        )
        await db_session.commit()

        retriever = MemoryRetriever(db_session, llm_provider)
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="水果",
            top_k=5,
            use_llm_classification=False,  # 禁用 LLM 分类
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieve_returns_correct_structure(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试检索结果结构正确"""
        from repositories import ResourceRepository

        # 直接创建资源
        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试内容",
            modality="text",
            description="这是测试描述",
            description_vector=fake_embedding,
            importance_score=5,
        )
        await db_session.commit()

        retriever = MemoryRetriever(db_session, llm_provider)
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试",
            top_k=5,
        )

        if len(results) > 0:
            result = results[0]
            assert "resource" in result
            assert "score" in result
            assert "strategy" in result
            assert isinstance(result["score"], float)


class TestVectorStrategy:
    """VectorStrategy 向量检索测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vector_search(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试向量检索"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建几个资源
        for i in range(3):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"内容{i}",
                modality="text",
                description=f"描述{i}",
                description_vector=fake_embedding,
                importance_score=5,
            )
        await db_session.commit()

        strategy = VectorStrategy(db_session, llm_provider)
        results = await strategy.search(
            user_id=test_user.id,
            query="测试查询",
            top_k=5,
        )

        assert len(results) <= 5
        for result in results:
            assert "resource" in result
            assert "score" in result
            assert "strategy" in result
            assert result["strategy"] == "vector"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vector_search_importance_filter(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试向量检索的重要性过滤"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建不同重要性的资源
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="低重要性",
            modality="text",
            description="低重要性描述",
            description_vector=fake_embedding,
            importance_score=1,
        )
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="高重要性",
            modality="text",
            description="高重要性描述",
            description_vector=fake_embedding,
            importance_score=10,
        )
        await db_session.commit()

        strategy = VectorStrategy(db_session, llm_provider)
        results = await strategy.search(
            user_id=test_user.id,
            query="描述",
            top_k=5,
            min_importance=5,  # 只返回重要性 >= 5 的
        )

        # 应该只有高重要性的资源
        for result in results:
            assert result["resource"].importance_score >= 5

    @pytest.mark.asyncio
    async def test_is_needed(self, db_session, llm_provider):
        """测试 is_needed 总是返回 True"""
        strategy = VectorStrategy(db_session, llm_provider)

        assert await strategy.is_needed("任何内容") is True


class TestRetrievalScore:
    """检索分数计算测试"""

    def test_calculate_retrieval_score(self, db_session, llm_provider):
        """测试检索分数计算"""
        retriever = MemoryRetriever(db_session, llm_provider)

        # 高相似度 + 高重要性
        score1 = retriever._calculate_retrieval_score(importance=10, similarity=1.0)
        assert score1 == 1.0  # 1.0 * 0.6 + 1.0 * 0.4 = 1.0

        # 低相似度 + 高重要性
        score2 = retriever._calculate_retrieval_score(importance=10, similarity=0.5)
        assert 0.5 < score2 < 1.0  # 0.5 * 0.6 + 1.0 * 0.4 = 0.7

        # 高相似度 + 低重要性
        score3 = retriever._calculate_retrieval_score(importance=1, similarity=1.0)
        assert 0.5 < score3 < 1.0  # 1.0 * 0.6 + 0.1 * 0.4 = 0.64

    def test_score_formula(self, db_session, llm_provider):
        """测试分数公式: similarity * 0.6 + importance_weight * 0.4"""
        retriever = MemoryRetriever(db_session, llm_provider)

        # 手动计算
        importance = 7
        similarity = 0.8
        expected = similarity * 0.6 + (importance / 10.0) * 0.4

        actual = retriever._calculate_retrieval_score(importance, similarity)
        assert abs(actual - expected) < 0.001


class TestRetrievalThresholds:
    """检索阈值测试"""

    def test_threshold_values(self):
        """测试四因子评分阈值常量值"""
        from services.retrieval.retriever import (
            FOUR_FACTOR_THRESHOLD_HIGH,
            FOUR_FACTOR_THRESHOLD_MEDIUM,
            FOUR_FACTOR_THRESHOLD_LOW,
        )
        assert FOUR_FACTOR_THRESHOLD_HIGH == 0.6
        assert FOUR_FACTOR_THRESHOLD_MEDIUM == 0.2
        assert FOUR_FACTOR_THRESHOLD_LOW == 0.1

    @pytest.mark.asyncio
    async def test_filter_by_threshold(self, db_session, llm_provider):
        """测试四因子评分阈值过滤"""
        retriever = MemoryRetriever(db_session, llm_provider)

        # 创建模拟结果（使用四因子评分值域）
        from tables import Resource

        results = [
            {
                "resource": Resource(
                    id="1",
                    user_id="test",
                    raw_content="高相关性",
                    description="描述",
                    importance_score=8,
                ),
                "score": 0.50,  # 高于阈值 FOUR_FACTOR_THRESHOLD_LOW (0.1)
            },
            {
                "resource": Resource(
                    id="2",
                    user_id="test",
                    raw_content="低相关性",
                    description="描述",
                    importance_score=8,
                ),
                "score": 0.05,  # 低于阈值 FOUR_FACTOR_THRESHOLD_LOW (0.1)
            },
        ]

        filtered = retriever._filter_by_threshold(results)

        # 低分数的结果应该被过滤
        assert len(filtered) == 1
        assert filtered[0]["score"] == 0.50


class TestBuildContext:
    """上下文构建测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_build_context(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试构建检索上下文"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="这是测试描述内容",
            description_vector=fake_embedding,
            importance_score=5,
        )
        await db_session.commit()

        retriever = MemoryRetriever(db_session, llm_provider)

        # 先检索
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试",
            top_k=5,
        )

        # 构建上下文
        context = await retriever.build_context_from_results(results, max_tokens=500)

        if results:
            assert isinstance(context, str)
            # 上下文应该包含描述
            if len(context) > 0:
                assert "描述" in context or "测试" in context

    @pytest.mark.asyncio
    async def test_build_context_empty(self, db_session, llm_provider):
        """测试空结果构建上下文"""
        retriever = MemoryRetriever(db_session, llm_provider)

        context = await retriever.build_context_from_results([], max_tokens=500)
        assert context == ""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_build_context_token_limit(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试上下文 token 限制"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建多个资源
        for i in range(10):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"内容{i}",
                modality="text",
                description=f"这是第{i}条测试描述，内容比较长以便测试token限制功能",
                description_vector=fake_embedding,
                importance_score=5,
            )
        await db_session.commit()

        retriever = MemoryRetriever(db_session, llm_provider)
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试",
            top_k=10,
        )

        # 设置很小的 token 限制
        context = await retriever.build_context_from_results(results, max_tokens=50)

        # 应该只包含部分结果
        assert len(context) < 500  # 粗略检查
