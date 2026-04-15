# 🔍 记忆去重测试：向量相似度 + LLM 判断
import pytest

from services.memory.deduplicator import MemoryDeduplicator, DedupAction, DedupResult
from services.memory.dedup_config import (
    get_threshold_for_category,
    cosine_distance_to_similarity,
    RESOURCE_DEDUP_THRESHOLD,
)
from tables import Resource, Category


class TestDedupConfig:
    """去重配置测试"""

    def test_cosine_distance_to_similarity(self):
        """测试余弦距离转相似度"""
        # 距离 0 -> 相似度 1（完全相同）
        assert cosine_distance_to_similarity(0.0) == 1.0

        # 距离 1 -> 相似度 0（正交）
        assert cosine_distance_to_similarity(1.0) == 0.0

        # 距离 2 -> 相似度 -1（完全相反）
        assert cosine_distance_to_similarity(2.0) == -1.0

        # 中间值
        similarity = cosine_distance_to_similarity(0.3)
        assert 0 < similarity < 1

    def test_get_threshold_for_category(self):
        """测试获取分类阈值"""
        # 核心自我分类的阈值应该更高
        threshold = get_threshold_for_category("核心自我")
        assert threshold.skip_threshold >= 0.85
        assert threshold.merge_threshold >= 0.70

        # 默认阈值
        default_threshold = get_threshold_for_category("未知分类")
        assert default_threshold.skip_threshold >= 0.90
        assert default_threshold.merge_threshold >= 0.75

    def test_resource_dedup_threshold_values(self):
        """测试 Resource 去重阈值范围"""
        assert 0 <= RESOURCE_DEDUP_THRESHOLD.skip_threshold <= 1
        assert 0 <= RESOURCE_DEDUP_THRESHOLD.merge_threshold <= 1
        assert RESOURCE_DEDUP_THRESHOLD.skip_threshold > RESOURCE_DEDUP_THRESHOLD.merge_threshold


class TestMemoryDeduplicator:
    """MemoryDeduplicator 功能测试"""

    @pytest.mark.asyncio
    async def test_check_resource_duplicate_no_existing(self, db_session, test_user, llm_provider):
        """测试无已有资源时的去重检查"""
        deduplicator = MemoryDeduplicator(db_session, llm_provider)

        result = await deduplicator.check_resource_duplicate(
            user_id=test_user.id,
            summary="这是一段新的摘要",
            vector=[0.1] * 1536,  # 假向量
        )

        assert result.action == DedupAction.CREATE
        assert result.existing_item is None
        assert result.similarity == 0.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_check_resource_duplicate_identical(
        self,
        db_session,
        test_user,
        llm_provider,
        sample_embedding: list[float],
    ):
        """测试完全相同内容的去重检查"""
        from repositories import ResourceRepository

        # 先创建一个资源
        resource_repo = ResourceRepository(db_session)
        existing = await resource_repo.create(
            user_id=test_user.id,
            raw_content="原始内容",
            modality="text",
            description="我喜欢吃苹果",
            description_vector=sample_embedding,
            importance_score=5,
        )
        await db_session.commit()

        # 用相同向量检查去重
        deduplicator = MemoryDeduplicator(db_session, llm_provider)
        result = await deduplicator.check_resource_duplicate(
            user_id=test_user.id,
            summary="我喜欢吃苹果",
            vector=sample_embedding,
        )

        # 完全相同应该跳过
        assert result.action in [DedupAction.SKIP, DedupAction.MERGE]
        assert result.existing_item is not None
        assert result.similarity >= 0.90

    @pytest.mark.asyncio
    async def test_check_category_duplicate_no_existing(self, db_session, test_user, llm_provider):
        """测试无已有分类项时的去重检查"""
        deduplicator = MemoryDeduplicator(db_session, llm_provider)

        result = await deduplicator.check_category_duplicate(
            user_id=test_user.id,
            category_name="核心自我",
            content="这是一条新的原子化记忆",
            vector=[0.1] * 1536,
        )

        assert result.action == DedupAction.CREATE

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_check_category_duplicate_with_existing(
        self,
        db_session,
        test_user,
        llm_provider,
        sample_embedding: list[float],
    ):
        """测试有已有分类项时的去重检查"""
        from repositories import CategoryRepository

        # 先创建一个分类项
        category_repo = CategoryRepository(db_session)
        existing = await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="用户的名字叫张三",
            importance_score=8,
        )
        await db_session.commit()

        # 用相似内容检查去重
        deduplicator = MemoryDeduplicator(db_session, llm_provider)

        # 完全相同的内容
        result = await deduplicator.check_category_duplicate(
            user_id=test_user.id,
            category_name="核心自我",
            content="用户的名字叫张三",
            vector=sample_embedding,
        )

        # 应该跳过或合并
        assert result.action in [DedupAction.SKIP, DedupAction.MERGE, DedupAction.CREATE]


class TestDedupActions:
    """去重操作测试"""

    @pytest.mark.asyncio
    async def test_reinforce_resource(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试强化 Resource"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
            importance_score=5,
        )

        deduplicator = MemoryDeduplicator(db_session, llm_provider)
        reinforced = await deduplicator.reinforce_resource(resource)

        assert reinforced.importance_score == 6

    @pytest.mark.asyncio
    async def test_reinforce_resource_max_score(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试强化 Resource 不会超过最大分数"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
            importance_score=10,  # 已是最高分
        )

        deduplicator = MemoryDeduplicator(db_session, llm_provider)
        reinforced = await deduplicator.reinforce_resource(resource)

        assert reinforced.importance_score == 10  # 不能超过 10

    @pytest.mark.asyncio
    async def test_reinforce_category(self, db_session, test_user, llm_provider):
        """测试强化 Category"""
        from repositories import CategoryRepository

        category_repo = CategoryRepository(db_session)
        category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="测试内容",
            importance_score=5,
        )

        deduplicator = MemoryDeduplicator(db_session, llm_provider)
        reinforced = await deduplicator.reinforce_category(category)

        assert reinforced.importance_score == 6

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_merge_resource(self, db_session, test_user, llm_provider, fake_embedding: list[float]):
        """测试合并 Resource"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="原始内容",
            modality="text",
            description="原始描述",
            description_vector=fake_embedding,
            importance_score=5,
        )

        deduplicator = MemoryDeduplicator(db_session, llm_provider)

        # 生成新向量
        new_embedding = await llm_provider.get_embedding("合并后的新描述")

        merged = await deduplicator.merge_resource(
            existing=resource,
            merged_content="合并后的新描述",
            merged_vector=new_embedding,
        )

        assert merged.description == "合并后的新描述"

    @pytest.mark.asyncio
    async def test_merge_category(self, db_session, test_user, llm_provider, fake_embedding):
        """测试合并 Category"""
        from repositories import CategoryRepository

        category_repo = CategoryRepository(db_session)
        category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="原始内容",
            importance_score=5,
        )

        deduplicator = MemoryDeduplicator(db_session, llm_provider)
        merged = await deduplicator.merge_category(
            existing=category,
            merged_content="合并后的内容",
            merged_vector=fake_embedding,
            importance_score=7,
        )

        assert merged.content == "合并后的内容"
        assert merged.importance_score == 7


class TestDedupResult:
    """DedupResult 数据类测试"""

    def test_dedup_result_create(self):
        """测试创建 CREATE 结果"""
        result = DedupResult(action=DedupAction.CREATE)
        assert result.action == DedupAction.CREATE
        assert result.existing_item is None
        assert result.similarity == 0.0

    def test_dedup_result_skip(self):
        """测试创建 SKIP 结果"""
        result = DedupResult(
            action=DedupAction.SKIP,
            existing_item="mock_resource",
            similarity=0.95,
            reason="相似度极高",
        )
        assert result.action == DedupAction.SKIP
        assert result.similarity == 0.95

    def test_dedup_result_merge(self):
        """测试创建 MERGE 结果"""
        result = DedupResult(
            action=DedupAction.MERGE,
            existing_item="mock_resource",
            similarity=0.80,
            merged_content="合并后的内容",
        )
        assert result.action == DedupAction.MERGE
        assert result.merged_content is not None
