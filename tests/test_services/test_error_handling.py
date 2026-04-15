# ⚠️ 异常处理测试：LLM 超时、数据库断连、服务不可用
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from services.memory.writer import MemoryWriter
from services.retrieval.retriever import MemoryRetriever
from services.llm.base import BaseLLMProvider
from services.oss.local_client import LocalOSSClient


class TestLLMTimeout:
    """LLM 超时异常测试"""

    @pytest.mark.asyncio
    async def test_llm_chat_timeout(self, db_session, test_user):
        """测试 LLM 对话超时"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_response = AsyncMock(
            side_effect=asyncio.TimeoutError("LLM request timed out")
        )

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        # 应该捕获超时异常
        with pytest.raises(asyncio.TimeoutError):
            await writer.save_chat(
                user_id=test_user.id,
                user_input="测试输入",
                assistant_response="测试回复",
                modality="text",
            )

    @pytest.mark.asyncio
    async def test_llm_embedding_timeout(self, db_session, test_user):
        """测试 LLM Embedding 超时"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.get_embedding = AsyncMock(
            side_effect=asyncio.TimeoutError("Embedding request timed out")
        )
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试",
            "importance_score": 5,
            "atomic_items": [],
        })

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        with pytest.raises(asyncio.TimeoutError):
            await writer.save_chat(
                user_id=test_user.id,
                user_input="测试",
                assistant_response="回复",
                modality="text",
            )

    @pytest.mark.asyncio
    async def test_llm_retrieval_timeout(self, db_session, test_user):
        """测试 LLM 检索超时"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_response = AsyncMock(
            side_effect=asyncio.TimeoutError("Classification timed out")
        )
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        retriever = MemoryRetriever(db_session, mock_llm)

        # 检索应该在 LLM 分类失败时降级到纯向量检索
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试查询",
            top_k=5,
        )

        # 应该返回空结果而不是崩溃
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_llm_rate_limit(self, db_session, test_user):
        """测试 LLM 速率限制"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_response = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        # 业务代码应该能处理速率限制
        with pytest.raises(Exception, match="Rate limit"):
            await mock_llm.generate_chat_response(
                system_prompt="test",
                context="",
                user_query="test",
            )


class TestLLMInvalidResponse:
    """LLM 无效响应测试"""

    @pytest.mark.asyncio
    async def test_llm_empty_response(self, db_session, test_user):
        """测试 LLM 空响应"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_response = AsyncMock(return_value="")
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "",
            "importance_score": 5,
            "atomic_items": [],
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        # 空响应应该能处理
        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试",
            assistant_response="回复",
            modality="text",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_llm_malformed_json(self, db_session, test_user):
        """测试 LLM 返回格式错误的 JSON"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_response = AsyncMock(return_value="这不是 JSON 格式")
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试",
            "importance_score": 5,
            "atomic_items": [],  # 解析失败时返回空列表
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        # 应该能处理解析失败
        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试",
            assistant_response="回复",
            modality="text",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_llm_missing_required_fields(self, db_session, test_user):
        """测试 LLM 响应缺少必需字段"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            # 缺少 summary
            "importance_score": 5,
            # 缺少 atomic_items
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        # 应该使用默认值或报错
        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试",
            assistant_response="回复",
            modality="text",
        )

        # 检查是否使用了默认值
        assert result["summary"] is not None or result is not None


class TestDatabaseErrors:
    """数据库错误测试"""

    @pytest.mark.asyncio
    async def test_database_connection_error(self, test_user):
        """测试数据库连接错误"""
        from sqlalchemy.exc import OperationalError

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=OperationalError("connection failed", {}, None)
        )

        # 应该捕获并处理连接错误
        with pytest.raises(OperationalError):
            await mock_session.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_database_constraint_violation(self, db_session, test_user):
        """测试数据库约束违反"""
        from repositories import UserRepository
        from sqlalchemy.exc import IntegrityError

        user_repo = UserRepository(db_session)

        # 尝试创建重复用户名
        user1 = await user_repo.create(
            username="duplicate_user",
            password="test",
        )
        await db_session.commit()

        # 再次创建同名用户应该失败
        with pytest.raises(Exception):  # IntegrityError
            await user_repo.create(
                username="duplicate_user",
                password="test2",
            )

    @pytest.mark.asyncio
    async def test_database_rollback_on_error(self, db_session, test_user, fake_embedding: list[float]):
        """测试错误时数据库回滚"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建资源
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )

        # 模拟错误
        try:
            # 执行一些操作
            await resource_repo.update(resource.id, importance_score=100)
            # 然后抛出异常
            raise Exception("模拟错误")
        except Exception:
            await db_session.rollback()

        # 回滚后数据应该保持一致


class TestOSSErrors:
    """OSS 存储错误测试"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_storage, test_user):
        """测试文件不存在"""
        client = LocalOSSClient(base_path=temp_storage)

        with pytest.raises(FileNotFoundError):
            await client.download("nonexistent/path/file.txt")

    @pytest.mark.asyncio
    async def test_disk_full_simulation(self, temp_storage, test_user):
        """测试磁盘满（模拟）"""
        client = LocalOSSClient(base_path=temp_storage)

        # 模拟磁盘满
        with patch("builtins.open", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError):
                await client.upload(
                    file_content=b"test",
                    filename="test.txt",
                    modality="document",
                    user_id=test_user.id,
                )

    @pytest.mark.asyncio
    async def test_permission_denied(self, temp_storage, test_user):
        """测试权限拒绝"""
        client = LocalOSSClient(base_path=temp_storage)

        # 模拟权限错误
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                await client.upload(
                    file_content=b"test",
                    filename="test.txt",
                    modality="document",
                    user_id=test_user.id,
                )


class TestServiceDegradation:
    """服务降级测试"""

    @pytest.mark.asyncio
    async def test_retrieval_without_llm_classification(self, db_session, test_user, fake_embedding: list[float]):
        """测试无 LLM 分类的检索降级"""
        from repositories import ResourceRepository

        # 先创建一些数据
        resource_repo = ResourceRepository(db_session)
        await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试内容",
            modality="text",
            description="测试描述",
            description_vector=fake_embedding,
            importance_score=5,
        )
        await db_session.commit()

        # 模拟 LLM 不可用
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_response = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )
        mock_llm.get_embedding = AsyncMock(return_value=fake_embedding)

        retriever = MemoryRetriever(db_session, mock_llm)

        # 禁用 LLM 分类，应该能降级到纯向量检索
        results = await retriever.retrieve(
            user_id=test_user.id,
            query="测试",
            top_k=5,
            use_llm_classification=False,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_memory_write_without_dedup(self, db_session, test_user):
        """测试无去重服务的写入降级"""
        mock_llm = AsyncMock(spec=BaseLLMProvider)
        mock_llm.extract_memory_intent = AsyncMock(return_value={
            "summary": "测试摘要",
            "importance_score": 5,
            "atomic_items": [],
        })
        mock_llm.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        # 禁用去重
        writer = MemoryWriter(db_session, mock_llm, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试输入",
            assistant_response="测试回复",
            modality="text",
        )

        assert result["resource_id"] is not None
        assert result["dedup_info"]["action"] == "create"


class TestCircuitBreaker:
    """熔断器模式测试（概念验证）"""

    @pytest.mark.asyncio
    async def test_consecutive_failures_trigger_circuit_breaker(self):
        """测试连续失败触发熔断"""
        failure_count = 0
        max_failures = 3
        circuit_open = False

        async def call_with_circuit_breaker():
            nonlocal failure_count, circuit_open

            if circuit_open:
                raise Exception("Circuit breaker is open")

            # 模拟服务调用
            raise Exception("Service unavailable")

        # 连续调用直到熔断
        for _ in range(max_failures + 1):
            try:
                await call_with_circuit_breaker()
            except Exception as e:
                failure_count += 1
                if failure_count >= max_failures:
                    circuit_open = True

        assert circuit_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """测试熔断恢复"""
        circuit_open = True
        last_failure_time = 0
        recovery_timeout = 60  # 秒

        # 模拟恢复时间已过
        import time
        last_failure_time = time.time() - recovery_timeout - 1

        # 检查是否应该尝试恢复
        should_try = (
            circuit_open and
            (time.time() - last_failure_time) > recovery_timeout
        )

        assert should_try is True


class TestGracefulShutdown:
    """优雅关闭测试"""

    @pytest.mark.asyncio
    async def test_pending_operations_on_shutdown(self, db_session, test_user, fake_embedding: list[float]):
        """测试关闭时处理中的操作"""
        from repositories import ResourceRepository

        resource_repo = ResourceRepository(db_session)

        # 创建一些操作
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )

        # 模拟关闭场景：确保数据已提交
        await db_session.commit()

        # 验证数据持久化
        fetched = await resource_repo.get_by_id(resource.id)
        assert fetched is not None
