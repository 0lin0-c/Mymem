# 🧪 测试配置：公共 fixtures
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from core.config import settings
from tables.base import Base
from tables import User
from repositories import UserRepository
from services.llm.factory import LLMFactory
from services.llm.base import BaseLLMProvider


# ============================================
# Event Loop (必须放在最前面，确保所有异步代码共享同一个 loop)
# ============================================

@pytest.fixture(scope="session")
def event_loop():
    """创建 session 级别的 event loop，确保所有异步测试共享同一个 loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ============================================
# 数据库 Fixtures
# ============================================

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """创建测试数据库引擎（session 级别，整个测试会话共享）"""
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

    # 创建所有表（如果不存在）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理：只清空数据，不删除表结构
    async with engine.begin() as conn:
        # 按依赖顺序清空表（先清空有外键依赖的表）
        await conn.execute(text("DELETE FROM resource_categories"))
        await conn.execute(text("DELETE FROM categories"))
        await conn.execute(text("DELETE FROM resources"))
        await conn.execute(text("DELETE FROM users"))

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话（每个测试函数独立）"""
    async_session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        # 测试结束后回滚，保持数据库干净
        await session.rollback()


# ============================================
# 用户 Fixtures
# ============================================

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """创建测试用户"""
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        username=f"test_user_{uuid.uuid4().hex[:8]}",
        password="test_password_hash",
        user_prompt_template="You are a helpful assistant.",
        agent_persona_template="You are a friendly AI companion.",
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession) -> User:
    """创建另一个测试用户（用于隔离测试）"""
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        username=f"another_user_{uuid.uuid4().hex[:8]}",
        password="another_password_hash",
    )
    await db_session.commit()
    return user


# ============================================
# LLM Fixtures
# ============================================

@pytest.fixture
def llm_provider() -> BaseLLMProvider:
    """获取真实 LLM Provider（用于集成测试）"""
    return LLMFactory.get_provider()


@pytest_asyncio.fixture
async def sample_embedding(llm_provider: BaseLLMProvider) -> list[float]:
    """获取一个真实的 embedding 向量样本（1536 维）"""
    embedding = await llm_provider.get_embedding("这是一个测试文本")
    return embedding


# ============================================
# 向量测试数据 Fixtures
# ============================================

@pytest.fixture
def fake_embedding() -> list[float]:
    """生成假的向量（维度从配置读取，用于不需要真实语义的测试）"""
    import random
    dim = settings.embedding_dimensions
    # 生成随机向量并归一化
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec]


@pytest.fixture
def similar_embeddings() -> tuple[list[float], list[float]]:
    """生成两个相似的向量（用于测试向量检索）"""
    import random
    dim = settings.embedding_dimensions

    # 基础向量
    base = [random.gauss(0, 1) for _ in range(dim)]
    norm = sum(x * x for x in base) ** 0.5
    base = [x / norm for x in base]

    # 添加小扰动生成相似向量
    similar = [x + random.gauss(0, 0.1) for x in base]
    norm = sum(x * x for x in similar) ** 0.5
    similar = [x / norm for x in similar]

    return base, similar


# ============================================
# 会话状态 Fixtures
# ============================================

@pytest.fixture
def session_id() -> str:
    """生成测试会话 ID"""
    return f"test_session_{uuid.uuid4().hex[:8]}"


# ============================================
# OSS 存储测试 Fixtures
# ============================================

@pytest.fixture
def temp_storage(tmp_path):
    """创建临时存储目录（自动清理）"""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    yield str(storage_dir)


# ============================================
# Pytest 配置
# ============================================

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "integration: 真实 API 调用的集成测试"
    )
    config.addinivalue_line(
        "markers", "slow: 运行较慢的测试"
    )
    config.addinivalue_line(
        "markers", "vector: 涉及向量计算的测试"
    )
    config.addinivalue_line(
        "markers", "redis: 需要 Redis 环境的测试"
    )
    config.addinivalue_line(
        "markers", "oss: 需要真实 OSS 配置的测试"
    )
