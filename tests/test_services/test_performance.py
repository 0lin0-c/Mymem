# ⚡ 性能测试：大量数据检索、批量写入、并发请求
import pytest
import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta

from repositories import ResourceRepository, CategoryRepository
from services.retrieval.retriever import MemoryRetriever
from services.memory.lifecycle import MemoryLifecycle


class TestBulkInsert:
    """批量写入性能测试"""

    @pytest.fixture
    async def bulk_resources(self, db_session, test_user, fake_embedding: list[float]):
        """创建大量测试资源"""
        resource_repo = ResourceRepository(db_session)
        resources = []

        for i in range(100):
            resource = await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"批量测试内容 {i}",
                modality="text",
                description=f"批量描述 {i} - 这是一个较长的描述文本，用于测试性能",
                description_vector=fake_embedding,
                importance_score=i % 10 + 1,
            )
            resources.append(resource)

        await db_session.commit()
        return resources

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_bulk_insert_performance(self, db_session, test_user, fake_embedding: list[float]):
        """测试批量插入性能"""
        resource_repo = ResourceRepository(db_session)

        start_time = time.time()
        batch_size = 50

        for i in range(batch_size):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"性能测试 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
                importance_score=5,
            )

        elapsed = time.time() - start_time

        # 50 条记录应该在 10 秒内完成
        assert elapsed < 10.0, f"批量插入耗时 {elapsed:.2f}s，超过阈值"
        print(f"\n批量插入 {batch_size} 条记录耗时: {elapsed:.2f}s")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_bulk_insert_with_commit(self, db_session, test_user, fake_embedding: list[float]):
        """测试批量插入并提交"""
        resource_repo = ResourceRepository(db_session)

        start_time = time.time()
        batch_size = 100

        for i in range(batch_size):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"测试 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
            )

        await db_session.commit()
        elapsed = time.time() - start_time

        print(f"\n批量插入并提交 {batch_size} 条记录耗时: {elapsed:.2f}s")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_bulk_category_insert(self, db_session, test_user):
        """测试批量分类插入"""
        category_repo = CategoryRepository(db_session)

        start_time = time.time()
        batch_size = 50

        for i in range(batch_size):
            await category_repo.create_item(
                user_id=test_user.id,
                category_name=f"测试分类 {i % 10}",
                content=f"原子化内容 {i}",
                importance_score=i % 10 + 1,
            )

        await db_session.commit()
        elapsed = time.time() - start_time

        print(f"\n批量插入 {batch_size} 条分类记录耗时: {elapsed:.2f}s")


class TestRetrievalPerformance:
    """检索性能测试"""

    @pytest.fixture
    async def setup_search_data(self, db_session, test_user, fake_embedding: list[float]):
        """准备检索测试数据"""
        resource_repo = ResourceRepository(db_session)

        # 创建不同重要性的资源
        for i in range(50):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"检索测试内容 {i} - 这是一段测试文本用于检索性能测试",
                modality="text",
                description=f"检索描述 {i} - 关键词: 测试, 检索, 性能",
                description_vector=fake_embedding,
                importance_score=i % 10 + 1,
            )

        await db_session.commit()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_vector_search_performance(
        self,
        db_session,
        test_user,
        fake_embedding: list[float],
        setup_search_data,
    ):
        """测试向量检索性能"""
        resource_repo = ResourceRepository(db_session)

        start_time = time.time()
        iterations = 10

        for _ in range(iterations):
            results = await resource_repo.search_by_vector(
                user_id=test_user.id,
                query_vector=fake_embedding,
                top_k=10,
            )

        elapsed = time.time() - start_time
        avg_time = elapsed / iterations

        print(f"\n向量检索平均耗时: {avg_time*1000:.2f}ms ({iterations} 次迭代)")
        assert avg_time < 1.0, f"向量检索平均耗时 {avg_time:.2f}s，超过阈值"

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_retrieval_with_llm_performance(
        self,
        db_session,
        test_user,
        llm_provider,
        setup_search_data,
    ):
        """测试带 LLM 分类的检索性能"""
        retriever = MemoryRetriever(db_session, llm_provider)

        start_time = time.time()

        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试检索查询",
            top_k=10,
            use_llm_classification=True,
        )

        elapsed = time.time() - start_time

        print(f"\n带 LLM 分类的检索耗时: {elapsed:.2f}s")
        # LLM 调用较慢，允许更长的时间
        assert elapsed < 30.0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_result_set(self, db_session, test_user, fake_embedding: list[float]):
        """测试大结果集处理"""
        resource_repo = ResourceRepository(db_session)

        # 创建大量数据
        for i in range(200):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"大数据集 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
                importance_score=5,
            )
        await db_session.commit()

        start_time = time.time()

        # 检索大结果集
        results = await resource_repo.get_by_user_id(test_user.id, limit=200)

        elapsed = time.time() - start_time

        print(f"\n获取 {len(results)} 条记录耗时: {elapsed:.2f}s")
        assert elapsed < 5.0


class TestConcurrentPerformance:
    """并发性能测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_reads(self, db_session, test_user, fake_embedding: list[float]):
        """测试并发读取性能"""
        resource_repo = ResourceRepository(db_session)

        # 准备数据
        for i in range(20):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"并发测试 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
            )
        await db_session.commit()

        async def read_operation():
            return await resource_repo.get_by_user_id(test_user.id)

        start_time = time.time()
        concurrent_count = 20

        tasks = [read_operation() for _ in range(concurrent_count)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        print(f"\n{concurrent_count} 次并发读取耗时: {elapsed:.2f}s")
        assert len(results) == concurrent_count

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_writes(self, db_session, test_user, fake_embedding: list[float]):
        """测试并发写入性能"""
        resource_repo = ResourceRepository(db_session)

        async def write_operation(suffix: int):
            return await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"并发写入 {suffix}",
                modality="text",
                description=f"描述 {suffix}",
                description_vector=fake_embedding,
            )

        start_time = time.time()
        concurrent_count = 20

        tasks = [write_operation(i) for i in range(concurrent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time

        successes = [r for r in results if not isinstance(r, Exception)]
        print(f"\n{concurrent_count} 次并发写入耗时: {elapsed:.2f}s, 成功: {len(successes)}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mixed_read_write(self, db_session, test_user, fake_embedding: list[float]):
        """测试混合读写性能"""
        resource_repo = ResourceRepository(db_session)

        # 准备初始数据
        for i in range(10):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"初始数据 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
            )
        await db_session.commit()

        async def read_op():
            return await resource_repo.get_by_user_id(test_user.id)

        async def write_op(suffix: int):
            return await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"写入数据 {suffix}",
                modality="text",
                description=f"描述 {suffix}",
                description_vector=fake_embedding,
            )

        start_time = time.time()

        # 50% 读取 + 50% 写入
        tasks = (
            [read_op() for _ in range(10)] +
            [write_op(i) for i in range(10, 20)]
        )
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time
        print(f"\n混合读写 20 次操作耗时: {elapsed:.2f}s")


class TestLifecyclePerformance:
    """生命周期操作性能测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_decay_calculation_performance(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试衰减计算性能"""
        resource_repo = ResourceRepository(db_session)

        # 创建大量资源
        for i in range(100):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"衰减测试 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
                importance_score=i % 10 + 1,
            )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)

        start_time = time.time()

        result = await lifecycle.decay_importance(test_user.id)

        elapsed = time.time() - start_time

        print(f"\n衰减计算 {result['resources']} 条资源耗时: {elapsed:.2f}s")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_stats_calculation_performance(
        self,
        db_session,
        test_user,
        llm_provider,
        fake_embedding: list[float],
    ):
        """测试统计计算性能"""
        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)

        # 创建大量数据
        for i in range(50):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"统计测试 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
            )
            await category_repo.create_item(
                user_id=test_user.id,
                category_name=f"分类 {i % 5}",
                content=f"内容 {i}",
            )
        await db_session.commit()

        lifecycle = MemoryLifecycle(db_session, llm_provider)

        start_time = time.time()

        stats = await lifecycle.get_memory_stats(test_user.id)

        elapsed = time.time() - start_time

        print(f"\n统计计算耗时: {elapsed:.2f}s")
        assert stats["resources"]["total"] >= 50


class TestMemoryUsage:
    """内存使用测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_vector_memory(self, db_session, test_user):
        """测试大量向量的内存使用"""
        import sys

        resource_repo = ResourceRepository(db_session)

        # 创建一个向量并检查大小
        vector = [0.1] * 1536
        vector_size = sys.getsizeof(vector)

        print(f"\n单个向量大小: {vector_size / 1024:.2f} KB")

        # 计算 1000 个向量的预估内存
        estimated_memory = vector_size * 1000 / 1024 / 1024
        print(f"1000 个向量预估内存: {estimated_memory:.2f} MB")

        # 应该在合理范围内
        assert estimated_memory < 100  # 不超过 100MB

    @pytest.mark.asyncio
    async def test_result_set_memory(self, db_session, test_user, fake_embedding: list[float]):
        """测试结果集内存使用"""
        resource_repo = ResourceRepository(db_session)

        # 创建数据
        for i in range(100):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"内存测试 {i}" * 10,  # 较长内容
                modality="text",
                description=f"描述 {i}" * 10,
                description_vector=fake_embedding,
            )
        await db_session.commit()

        # 获取结果集
        results = await resource_repo.get_by_user_id(test_user.id, limit=100)

        # 检查结果集大小
        import sys
        result_size = sys.getsizeof(results)

        print(f"\n100 条结果集大小: {result_size / 1024:.2f} KB")


class TestIndexPerformance:
    """索引性能测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_importance_filter_performance(
        self,
        db_session,
        test_user,
        fake_embedding: list[float],
    ):
        """测试重要性过滤性能（应有索引）"""
        resource_repo = ResourceRepository(db_session)

        # 创建不同重要性的数据
        for i in range(100):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"索引测试 {i}",
                modality="text",
                description=f"描述 {i}",
                description_vector=fake_embedding,
                importance_score=i % 10 + 1,
            )
        await db_session.commit()

        start_time = time.time()

        # 按重要性过滤
        high_importance = await resource_repo.get_by_importance_range(
            user_id=test_user.id,
            min_score=7,
            max_score=10,
            limit=100,
        )

        elapsed = time.time() - start_time

        print(f"\n重要性过滤耗时: {elapsed*1000:.2f}ms")
        assert elapsed < 1.0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_modality_filter_performance(
        self,
        db_session,
        test_user,
        fake_embedding: list[float],
    ):
        """测试模态过滤性能"""
        resource_repo = ResourceRepository(db_session)

        # 创建不同模态的数据
        modalities = ["text", "image", "voice"]
        for i in range(90):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"模态测试 {i}",
                modality=modalities[i % 3],
                description=f"描述 {i}",
                description_vector=fake_embedding,
            )
        await db_session.commit()

        start_time = time.time()

        text_resources = await resource_repo.get_by_modality(
            user_id=test_user.id,
            modality="text",
            limit=100,
        )

        elapsed = time.time() - start_time

        print(f"\n模态过滤耗时: {elapsed*1000:.2f}ms")
        assert elapsed < 1.0
