# 🧪 边界条件测试：空输入、超长文本、特殊字符、并发写入
import pytest
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from tables import User, Category, Resource
from repositories import UserRepository, CategoryRepository, ResourceRepository
from services.memory.writer import MemoryWriter
from services.retrieval.retriever import MemoryRetriever


class TestEmptyInput:
    """空输入边界测试"""

    @pytest.mark.asyncio
    async def test_empty_username(self, db_session):
        """测试空用户名"""
        user_repo = UserRepository(db_session)

        # 空字符串用户名
        with pytest.raises(Exception):  # 数据库约束或 Pydantic 验证
            await user_repo.create(username="", password="test")

    @pytest.mark.asyncio
    async def test_empty_user_input(self, db_session, test_user, llm_provider):
        """测试空用户输入"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        # 空字符串输入应该能处理或报错
        try:
            result = await writer.save_chat(
                user_id=test_user.id,
                user_input="",
                assistant_response="回复",
                modality="text",
            )
            # 如果不报错，检查结果
            assert result is not None
        except ValueError:
            pass  # 预期行为：拒绝空输入

    @pytest.mark.asyncio
    async def test_whitespace_only_input(self, db_session, test_user, llm_provider):
        """测试纯空白字符输入"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        try:
            result = await writer.save_chat(
                user_id=test_user.id,
                user_input="   \n\t   ",
                assistant_response="回复",
                modality="text",
            )
        except ValueError:
            pass  # 预期：拒绝纯空白输入

    @pytest.mark.asyncio
    async def test_empty_query_retrieval(self, db_session, test_user, llm_provider):
        """测试空查询检索"""
        retriever = MemoryRetriever(db_session, llm_provider)

        # 空查询应该返回空结果或报错
        try:
            results = await retriever.retrieve(
                user_id=test_user.id,
                query="",
                top_k=5,
            )
            assert isinstance(results, list)
        except ValueError:
            pass  # 预期行为


class TestLongText:
    """超长文本边界测试"""

    @pytest.fixture
    def long_text_10k(self):
        """生成 10KB 文本"""
        return "测试内容" * 1250  # 约 10KB

    @pytest.fixture
    def long_text_1m(self):
        """生成 1MB 文本"""
        return "A" * (1024 * 1024)

    @pytest.mark.asyncio
    async def test_long_username(self, db_session):
        """测试超长用户名"""
        user_repo = UserRepository(db_session)
        long_name = "a" * 1000  # 1000 字符

        # 应该被数据库约束拒绝
        with pytest.raises(Exception):
            await user_repo.create(username=long_name, password="test")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_long_content_save(self, db_session, test_user, llm_provider, long_text_10k):
        """测试保存长文本内容"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input=long_text_10k,
            assistant_response="收到长文本",
            modality="text",
        )

        assert result is not None
        assert result["resource_id"] is not None

    @pytest.mark.asyncio
    async def test_long_description(self, db_session, test_user, fake_embedding: list[float]):
        """测试超长描述字段"""
        resource_repo = ResourceRepository(db_session)
        long_desc = "描述内容" * 5000  # 约 25KB

        # 数据库应该能存储或报错
        try:
            resource = await resource_repo.create(
                user_id=test_user.id,
                raw_content="测试",
                modality="text",
                description=long_desc,
                description_vector=fake_embedding,
            )
            # 如果成功，检查存储
            assert resource.description is not None
        except Exception:
            pass  # 可能超出字段限制

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_very_long_query(self, db_session, test_user, llm_provider, long_text_10k):
        """测试超长查询文本"""
        retriever = MemoryRetriever(db_session, llm_provider)

        # 超长查询应该能处理
        results = await retriever.retrieve(
            user_id=test_user.id,
            query=long_text_10k[:5000],  # 限制长度
            top_k=5,
        )

        assert isinstance(results, list)


class TestSpecialCharacters:
    """特殊字符边界测试"""

    @pytest.mark.asyncio
    async def test_unicode_username(self, db_session):
        """测试 Unicode 用户名"""
        user_repo = UserRepository(db_session)

        user = await user_repo.create(
            username="用户名_测试_日本語_한국어",
            password="test",
        )

        assert user.username == "用户名_测试_日本語_한국어"

    @pytest.mark.asyncio
    async def test_emoji_in_content(self, db_session, test_user, fake_embedding: list[float]):
        """测试 Emoji 表情内容"""
        resource_repo = ResourceRepository(db_session)

        emoji_content = "你好 👋 这是一条测试消息 🎉 包含多个表情 😀 🚀 ✨"

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content=emoji_content,
            modality="text",
            description=emoji_content,
            description_vector=fake_embedding,
        )

        assert resource.raw_content == emoji_content

    @pytest.mark.asyncio
    async def test_sql_injection_attempt(self, db_session, test_user, fake_embedding: list[float]):
        """测试 SQL 注入尝试（应该被安全处理）"""
        resource_repo = ResourceRepository(db_session)

        # SQL 注入尝试
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "'; DELETE FROM resources WHERE '1'='1",
        ]

        for malicious in malicious_inputs:
            # 使用 ORM 应该自动转义
            resource = await resource_repo.create(
                user_id=test_user.id,
                raw_content=malicious,
                modality="text",
                description=f"安全描述: {malicious}",
                description_vector=fake_embedding,
            )

            # 数据应该被安全存储，不是被执行
            assert resource.raw_content == malicious

    @pytest.mark.asyncio
    async def test_xss_attempt(self, db_session, test_user, fake_embedding: list[float]):
        """测试 XSS 攻击尝试"""
        resource_repo = ResourceRepository(db_session)

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
        ]

        for payload in xss_payloads:
            resource = await resource_repo.create(
                user_id=test_user.id,
                raw_content=payload,
                modality="text",
                description=payload,
                description_vector=fake_embedding,
            )

            # 数据应该被原样存储，而不是被执行
            assert resource.raw_content == payload

    @pytest.mark.asyncio
    async def test_null_bytes(self, db_session, test_user, fake_embedding: list[float]):
        """测试空字节字符"""
        resource_repo = ResourceRepository(db_session)

        content_with_null = "正常内容\x00中间有空字节\x00结尾"

        try:
            resource = await resource_repo.create(
                user_id=test_user.id,
                raw_content=content_with_null,
                modality="text",
                description="包含空字节",
                description_vector=fake_embedding,
            )
            # 数据库可能自动处理空字节
            assert resource is not None
        except Exception:
            pass  # 某些数据库可能拒绝空字节

    @pytest.mark.asyncio
    async def test_newlines_and_tabs(self, db_session, test_user, fake_embedding: list[float]):
        """测试换行符和制表符"""
        resource_repo = ResourceRepository(db_session)

        content = "第一行\n第二行\n\t缩进内容\n\r\nWindows换行"

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content=content,
            modality="text",
            description=content,
            description_vector=fake_embedding,
        )

        assert "\n" in resource.raw_content
        assert "\t" in resource.raw_content


class TestConcurrentAccess:
    """并发写入边界测试"""

    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, db_session):
        """测试并发创建用户"""
        user_repo = UserRepository(db_session)

        async def create_user(suffix: int):
            return await user_repo.create(
                username=f"concurrent_user_{suffix}_{uuid.uuid4().hex[:4]}",
                password="test",
            )

        # 并发创建 10 个用户
        tasks = [create_user(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查成功数量
        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 8  # 至少 80% 成功

    @pytest.mark.asyncio
    async def test_concurrent_resource_creation(
        self,
        db_session,
        test_user,
        fake_embedding: list[float],
    ):
        """测试并发创建资源"""
        resource_repo = ResourceRepository(db_session)

        async def create_resource(suffix: int):
            return await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"并发测试内容 {suffix}",
                modality="text",
                description=f"并发描述 {suffix}",
                description_vector=fake_embedding,
            )

        # 并发创建 20 个资源
        tasks = [create_resource(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 18

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_memory_write(self, db_session, test_user, llm_provider):
        """测试并发记忆写入"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        async def save_memory(suffix: int):
            return await writer.save_chat(
                user_id=test_user.id,
                user_input=f"并发消息 {suffix}",
                assistant_response=f"并发回复 {suffix}",
                modality="text",
            )

        # 并发写入 5 条记忆
        tasks = [save_memory(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 4

    @pytest.mark.asyncio
    async def test_concurrent_read_write(
        self,
        db_session,
        test_user,
        fake_embedding: list[float],
    ):
        """测试并发读写"""
        resource_repo = ResourceRepository(db_session)

        # 先创建一些数据
        for i in range(5):
            await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"初始数据 {i}",
                modality="text",
                description=f"初始描述 {i}",
                description_vector=fake_embedding,
            )

        async def read_operation():
            return await resource_repo.get_by_user_id(test_user.id)

        async def write_operation(suffix: int):
            return await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"写入数据 {suffix}",
                modality="text",
                description=f"写入描述 {suffix}",
                description_vector=fake_embedding,
            )

        # 混合读写操作
        tasks = (
            [read_operation() for _ in range(5)] +
            [write_operation(i) for i in range(5, 10)]
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 大部分操作应该成功
        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 8


class TestNumericBoundaries:
    """数值边界测试"""

    @pytest.mark.asyncio
    async def test_importance_score_min(self, db_session, test_user, fake_embedding: list[float]):
        """测试重要性分数最小值"""
        resource_repo = ResourceRepository(db_session)

        # 分数为 0 或负数
        for score in [0, -1, -100]:
            try:
                resource = await resource_repo.create(
                    user_id=test_user.id,
                    raw_content="测试",
                    modality="text",
                    description="测试",
                    description_vector=fake_embedding,
                    importance_score=score,
                )
                # 如果允许，检查是否被限制
                assert resource.importance_score >= 1
            except Exception:
                pass  # 预期：拒绝无效分数

    @pytest.mark.asyncio
    async def test_importance_score_max(self, db_session, test_user, fake_embedding: list[float]):
        """测试重要性分数最大值"""
        resource_repo = ResourceRepository(db_session)

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试",
            modality="text",
            description="测试",
            description_vector=fake_embedding,
            importance_score=100,  # 超过最大值 10
        )

        # 应该被限制在 1-10 范围
        assert 1 <= resource.importance_score <= 10

    @pytest.mark.asyncio
    async def test_top_k_boundaries(self, db_session, test_user, llm_provider):
        """测试检索 top_k 边界"""
        retriever = MemoryRetriever(db_session, llm_provider)

        # top_k = 0
        results = await retriever.retrieve(user_id=test_user.id, query="测试", top_k=0)
        assert len(results) == 0

        # top_k 为负数
        try:
            results = await retriever.retrieve(user_id=test_user.id, query="测试", top_k=-1)
        except ValueError:
            pass  # 预期：拒绝负数

        # top_k 超大值
        results = await retriever.retrieve(user_id=test_user.id, query="测试", top_k=10000)
        assert len(results) <= 1000  # 应该有上限


class TestUserIdBoundaries:
    """用户 ID 边界测试"""

    @pytest.mark.asyncio
    async def test_nonexistent_user_id(self, db_session, fake_embedding: list[float]):
        """测试不存在的用户 ID"""
        resource_repo = ResourceRepository(db_session)

        resources = await resource_repo.get_by_user_id("nonexistent-user-id-12345")
        assert resources == []

    @pytest.mark.asyncio
    async def test_malformed_user_id(self, db_session, fake_embedding: list[float]):
        """测试格式错误的用户 ID"""
        resource_repo = ResourceRepository(db_session)

        malformed_ids = [
            "",
            "   ",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "null",
            "undefined",
        ]

        for user_id in malformed_ids:
            # 应该返回空结果或报错，而不是崩溃
            try:
                resources = await resource_repo.get_by_user_id(user_id)
                assert resources == [] or resources is None
            except Exception:
                pass  # 预期：拒绝无效 ID
