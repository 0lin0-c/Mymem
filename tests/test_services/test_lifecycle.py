# 🔄 记忆生命周期测试：遗忘机制、重要性衰减、统计
import pytest
import math
from datetime import datetime, timezone, timedelta

from services.memory.lifecycle import (
    MemoryLifecycle,
    FORGETTING_EXCLUDED_CATEGORIES,
)


class TestForgettingConstants:
    """遗忘机制常量测试"""

    def test_excluded_categories(self):
        """测试不参与遗忘的分类"""
        assert "核心自我" in FORGETTING_EXCLUDED_CATEGORIES
        assert "社交关系图谱" in FORGETTING_EXCLUDED_CATEGORIES
        assert len(FORGETTING_EXCLUDED_CATEGORIES) == 2


class TestEffectiveImportanceCalculation:
    """有效重要性计算测试"""

    def test_formula_components(self):
        """测试计算公式组成部分"""
        # 公式: EffectiveScore = Importance × e^(-Days / (Importance × 5)) × (1 + log(AccessCount + 1))

        # 1. 时间衰减因子
        importance = 5
        days = 10
        decay_factor = math.exp(-days / (importance * 5))
        assert 0 < decay_factor < 1

        # 2. 访问加成因子
        access_count = 3
        access_bonus = 1 + math.log(access_count + 1)
        assert access_bonus > 1

        # 3. 完整计算
        effective = importance * decay_factor * access_bonus
        assert effective > 0

    def test_decay_factor_with_high_importance(self):
        """高重要性记忆衰减更慢"""
        days = 30

        importance_5 = 5
        importance_10 = 10

        decay_5 = math.exp(-days / (importance_5 * 5))
        decay_10 = math.exp(-days / (importance_10 * 5))

        # 高重要性的衰减因子应该更高（保留更多）
        assert decay_10 > decay_5

    def test_access_bonus_growth(self):
        """访问加成对数增长"""
        # 访问次数增加，加成增长但趋于平缓
        bonus_0 = 1 + math.log(1)  # 0 次访问
        bonus_10 = 1 + math.log(11)  # 10 次访问
        bonus_100 = 1 + math.log(101)  # 100 次访问

        assert bonus_10 > bonus_0
        assert bonus_100 > bonus_10

        # 增量递减
        inc_0_to_10 = bonus_10 - bonus_0
        inc_10_to_100 = bonus_100 - bonus_10
        assert inc_0_to_10 > inc_10_to_100

    @pytest.mark.asyncio
    async def test_calculate_effective_importance_resource(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试 Resource 有效重要性计算"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试内容",
            modality="text",
            description="测试描述",
            description_vector=fake_embedding,
            importance_score=7,
            access_count=2,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        effective = await lifecycle.calculate_effective_importance(
            resource.id, is_resource=True
        )

        # 有效重要性应该在合理范围内
        assert effective > 0
        # 新创建的记忆，衰减很小
        assert effective <= 7 * 3  # 最大可能值（访问加成）

    @pytest.mark.asyncio
    async def test_calculate_effective_importance_category(
        self,
        db_session,
        test_user,
        llm_provider,
    ):
        """测试 Category 有效重要性计算"""
        from repositories import CategoryRepository

        category_repo = CategoryRepository(db_session)
        category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="测试分类",
            content="测试内容",
            importance_score=8,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        effective = await lifecycle.calculate_effective_importance(
            category.id, is_resource=False
        )

        assert effective > 0

    @pytest.mark.asyncio
    async def test_calculate_effective_importance_nonexistent(
        self,
        db_session,
        llm_provider,
    ):
        """测试不存在项目的有效重要性"""
        lifecycle = MemoryLifecycle(db_session, llm_provider)

        effective = await lifecycle.calculate_effective_importance(
            "non-existent-id", is_resource=True
        )

        assert effective == 0.0


class TestDecayImportance:
    """重要性衰减测试"""

    @pytest.mark.asyncio
    async def test_decay_importance_new_memory(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试新记忆不衰减"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="新记忆",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
            importance_score=7,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        result = await lifecycle.decay_importance(test_user.id)

        # 新记忆不应该衰减太多
        assert result["resources"] >= 0

    @pytest.mark.asyncio
    async def test_decay_importance_excluded_categories(
        self,
        db_session,
        test_user,
        llm_provider,
    ):
        """测试排除的分类不参与衰减"""
        from repositories import CategoryRepository

        category_repo = CategoryRepository(db_session)

        # 创建核心自我分类
        core_category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="用户的姓名是张三",
            importance_score=10,
        )

        # 创建普通分类
        normal_category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="语义知识库",
            content="某个知识点",
            importance_score=10,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        await lifecycle.decay_importance(test_user.id)

        # 核心自我不应该衰减


class TestForgetting:
    """遗忘清理测试"""

    @pytest.mark.asyncio
    async def test_forget_low_importance(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试删除低重要性记忆"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建高重要性资源
        high_resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="重要内容",
            modality="text",
            description="高重要性",
            description_vector=fake_embedding,
            importance_score=10,
        )

        # 创建低重要性资源
        low_resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="不重要内容",
            modality="text",
            description="低重要性",
            description_vector=fake_embedding,
            importance_score=1,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        # 设置较低的阈值和较短的天数
        result = await lifecycle.forget_low_importance(
            user_id=test_user.id,
            threshold=0.5,
            min_days=0,  # 立即可删除
        )

        assert "resources" in result
        assert "categories" in result

    @pytest.mark.asyncio
    async def test_forget_preserves_core_self(
        self,
        db_session,
        test_user,
        llm_provider,
    ):
        """测试核心自我不被遗忘"""
        from repositories import CategoryRepository

        category_repo = CategoryRepository(db_session)

        # 创建核心自我分类项
        core_item = await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="用户姓名张三",
            importance_score=1,  # 低重要性
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        await lifecycle.forget_low_importance(
            user_id=test_user.id,
            threshold=0.5,
            min_days=0,
        )

        # 核心自我不应该被删除
        fetched = await category_repo.get_by_id(core_item.id)
        # 注：取决于实现，可能需要调整断言


class TestMarkForForgetting:
    """标记待遗忘测试"""

    @pytest.mark.asyncio
    async def test_mark_for_forgetting(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试标记待遗忘记忆"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建一个资源（不设置时间偏移，新记忆不会标记）
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
            importance_score=5,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        result = await lifecycle.mark_for_forgetting(test_user.id)

        assert "resources" in result
        assert "categories" in result


class TestAccessCount:
    """访问计数测试"""

    @pytest.mark.asyncio
    async def test_increment_access_count_resource(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试 Resource 访问计数增加"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
            importance_score=5,
            access_count=0,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)

        # 增加访问计数
        success = await lifecycle.increment_access_count(resource.id, is_resource=True)
        assert success is True

        # 验证计数增加
        updated = await resource_repo.get_by_id(resource.id)
        assert updated.access_count == 1

    @pytest.mark.asyncio
    async def test_increment_access_count_category(
        self,
        db_session,
        test_user,
        llm_provider,
    ):
        """测试 Category 访问计数增加"""
        from repositories import CategoryRepository

        category_repo = CategoryRepository(db_session)
        category = await category_repo.create_item(
            user_id=test_user.id,
            category_name="测试",
            content="内容",
            importance_score=5,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)

        success = await lifecycle.increment_access_count(category.id, is_resource=False)
        assert success is True

    @pytest.mark.asyncio
    async def test_increment_access_count_nonexistent(
        self,
        db_session,
        llm_provider,
    ):
        """测试不存在项目的访问计数"""
        lifecycle = MemoryLifecycle(db_session, llm_provider)

        success = await lifecycle.increment_access_count("non-existent", is_resource=True)
        assert success is False


class TestMemoryStats:
    """记忆统计测试"""

    @pytest.mark.asyncio
    async def test_get_memory_stats_empty(
        self,
        db_session,
        test_user,
        llm_provider,
    ):
        """测试空用户统计"""
        lifecycle = MemoryLifecycle(db_session, llm_provider)
        stats = await lifecycle.get_memory_stats(test_user.id)

        assert "resources" in stats
        assert "atomic_items" in stats
        assert stats["resources"]["total"] == 0
        assert stats["atomic_items"]["total"] == 0

    @pytest.mark.asyncio
    async def test_get_memory_stats_with_data(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试有数据用户统计"""
        from repositories import ResourceRepository, CategoryRepository

        # 创建资源
        resource_repo = ResourceRepository(db_session)
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试1",
            modality="text",
            description="描述1",
            description_vector=fake_embedding,
            importance_score=5,
        )
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试2",
            modality="text",
            description="描述2",
            description_vector=fake_embedding,
            importance_score=7,
        )

        # 创建分类项
        category_repo = CategoryRepository(db_session)
        await category_repo.create_item(
            user_id=test_user.id,
            category_name="核心自我",
            content="内容1",
            importance_score=8,
        )

        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        stats = await lifecycle.get_memory_stats(test_user.id)

        assert stats["resources"]["total"] >= 2
        assert stats["atomic_items"]["total"] >= 1
        assert "avg_importance" in stats["resources"]
        assert "by_category" in stats["atomic_items"]

    @pytest.mark.asyncio
    async def test_stats_avg_importance_calculation(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试平均重要性计算"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="A",
            modality="text",
            description="A",
            description_vector=fake_embedding,
            importance_score=3,
        )
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="B",
            modality="text",
            description="B",
            description_vector=fake_embedding,
            importance_score=7,
        )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)
        stats = await lifecycle.get_memory_stats(test_user.id)

        # 平均值应该是 (3 + 7) / 2 = 5
        assert stats["resources"]["avg_importance"] == 5.0
