# 🧪 测试配置：公共 fixtures
import asyncio
import uuid
from typing import AsyncGenerator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from core.config import settings
from tables.base import Base
from tables import User
from repositories import UserRepository
from services.llm.factory import LLMFactory
from services.llm.base import BaseLLMProvider


REAL_DB_NAME_HINTS = {"postgres", "prod", "production", "main", "mymem"}
NON_REAL_DB_TOKENS = ("test", "pytest", "tmp", "temporary")


def _extract_database_name(database_url: str) -> str:
    parsed = urlparse(database_url)
    return parsed.path.rsplit("/", 1)[-1].lower().strip()


def _looks_like_real_database(database_url: str) -> bool:
    lowered = database_url.lower()
    db_name = _extract_database_name(database_url)
    if any(token in lowered for token in NON_REAL_DB_TOKENS):
        return False
    return db_name in REAL_DB_NAME_HINTS


def _converted_eval_requested(pytestconfig: pytest.Config) -> bool:
    return bool(
        pytestconfig.getoption("--converted-sample") is not None
        or pytestconfig.getoption("--converted-all")
    )


def _personamem_v2_eval_requested(pytestconfig: pytest.Config) -> bool:
    return bool(pytestconfig.getoption("--personamem-v2"))


def _converted_eval_requires_write(pytestconfig: pytest.Config) -> bool:
    retrieval_only = pytestconfig.getoption("--converted-retrieval-only")
    import_only = pytestconfig.getoption("--converted-import-only")
    reset_memory = pytestconfig.getoption("--converted-reset-memory")
    return bool(import_only or reset_memory or not retrieval_only)


def _personamem_v2_eval_requires_write(pytestconfig: pytest.Config) -> bool:
    retrieval_only = pytestconfig.getoption("--personamem-v2-retrieval-only")
    import_only = pytestconfig.getoption("--personamem-v2-import-only")
    reset_memory = pytestconfig.getoption("--personamem-v2-reset-memory")
    return bool(import_only or reset_memory or not retrieval_only)


def _assert_real_db_usage_is_safe(pytestconfig: pytest.Config) -> None:
    database_url = settings.database_url
    if not _looks_like_real_database(database_url):
        return

    allow_real_db_write = pytestconfig.getoption("--allow-real-db-write")
    is_converted_eval = _converted_eval_requested(pytestconfig)
    is_personamem_v2_eval = _personamem_v2_eval_requested(pytestconfig)

    if is_converted_eval:
        if _converted_eval_requires_write(pytestconfig) and not allow_real_db_write:
            raise pytest.UsageError(
                "Refusing to run a write-path converted_data evaluation against the real database. "
                "Use --converted-retrieval-only for read-only evaluation, or add "
                "--allow-real-db-write only when you explicitly want to re-import/reset memory."
            )
        return

    if is_personamem_v2_eval:
        if _personamem_v2_eval_requires_write(pytestconfig) and not allow_real_db_write:
            raise pytest.UsageError(
                "Refusing to run a write-path PersonaMem-v2 evaluation against the real database. "
                "Use --personamem-v2-retrieval-only for read-only evaluation, or add "
                "--allow-real-db-write only when you explicitly want to import/reset memory."
            )
        return

    if not allow_real_db_write:
        raise pytest.UsageError(
            "Refusing to run regular pytest database fixtures against the real database. "
            "Use a test database, or rerun with --allow-real-db-write only when you explicitly "
            "intend to modify real DB data."
        )


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
async def db_engine(pytestconfig: pytest.Config):
    """创建测试数据库引擎（session 级别，整个测试会话共享）"""
    _assert_real_db_usage_is_safe(pytestconfig)
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

    # 创建所有表（如果不存在）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 重要：无论是否真实库，pytest 结束时都不再自动清表。
    # 真实库默认只读；写路径由显式 reset/reimport 命令控制，而不是 fixture teardown。

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

def pytest_addoption(parser):
    """统一 converted_data 评估入口的 pytest 参数。"""
    group = parser.getgroup("converted_data")
    group.addoption("--converted-sample", type=int, help="运行指定 converted_data sample")
    group.addoption("--converted-all", action="store_true", help="运行所有 converted_data samples")
    group.addoption(
        "--converted-data-dir",
        type=str,
        help="指定 converted_data 数据目录，默认使用 data/converted_data_zh",
    )
    group.addoption(
        "--converted-eval-mode",
        choices=["storage_eval", "retrieval_eval", "assistant_eval"],
        default="assistant_eval",
        help="converted_data 评估模式",
    )
    group.addoption("--converted-top-k", type=int, default=10, help="检索 top_k")
    group.addoption("--converted-character", type=str, help="只评估指定角色")
    group.addoption("--converted-import-only", action="store_true", help="只导入，不评估")
    group.addoption("--converted-retrieval-only", action="store_true", help="跳过导入，只评估")
    group.addoption("--converted-reset-memory", action="store_true", help="导入前清空该测试用户记忆")
    group.addoption("--converted-no-dedup", action="store_true", help="禁用记忆去重")
    group.addoption("--converted-max-questions", type=int, help="限制每个角色的 QA 数量，用于端到端冒烟测试")
    group.addoption("--converted-postprocess-bad-cases", action="store_true", help="主评估完成后再补做失败样本的 bad-case diagnosis")
    personamem = parser.getgroup("personamem_v2")
    personamem.addoption("--personamem-v2", action="store_true", help="启用 PersonaMem-v2 text snippet 评估")
    personamem.addoption("--personamem-v2-split", type=str, default="benchmark_text", help="PersonaMem-v2 split")
    personamem.addoption("--personamem-v2-max-personas", type=int, default=2, help="限制 persona 数量")
    personamem.addoption("--personamem-v2-max-questions", type=int, default=5, help="限制每个 persona 的问题数")
    personamem.addoption("--personamem-v2-max-rows", type=int, default=100, help="限制加载的原始行数")
    personamem.addoption("--personamem-v2-persona-id", type=str, help="只评估指定 PersonaMem persona_id")
    personamem.addoption(
        "--personamem-v2-eval-mode",
        choices=["storage_eval", "retrieval_eval", "assistant_eval"],
        default="assistant_eval",
        help="PersonaMem-v2 评估模式",
    )
    personamem.addoption("--personamem-v2-top-k", type=int, default=10, help="检索 top_k")
    personamem.addoption("--personamem-v2-import-only", action="store_true", help="只导入，不评估")
    personamem.addoption("--personamem-v2-retrieval-only", action="store_true", help="跳过导入，只评估")
    personamem.addoption("--personamem-v2-reset-memory", action="store_true", help="导入前清空该 persona 用户记忆")
    personamem.addoption("--personamem-v2-no-dedup", action="store_true", help="禁用记忆去重")
    personamem.addoption("--personamem-v2-no-save-raw-snapshot", action="store_true", help="不保存原始 rows 快照")
    personamem.addoption(
        "--personamem-v2-evaluator-model",
        type=str,
        help="Fixed PersonaMem-v2 evaluator model for answer correctness.",
    )
    personamem.addoption(
        "--personamem-v2-model-sweep",
        type=str,
        help="Comma-separated CHAT_MODEL list, or 'default' for the five planned model comparisons.",
    )
    personamem.addoption("--personamem-v2-orthogonal", action="store_true", help="Run PersonaMem-v2 orthogonal replay eval.")
    personamem.addoption(
        "--personamem-v2-orthogonal-mode",
        choices=["writer_ab", "retrieval_ab", "rerank_ab", "generator_ab", "e2e_diagnostic"],
        default="retrieval_ab",
        help="PersonaMem-v2 orthogonal experiment type.",
    )
    personamem.addoption("--personamem-v2-baseline-snapshot", type=str, help="Path to baseline snapshot JSON.")
    personamem.addoption("--personamem-v2-candidate-config", type=str, help="Path to orthogonal candidate config JSON.")
    personamem.addoption("--personamem-v2-output-dir", type=str, help="Output directory for PersonaMem-v2 orthogonal reports.")
    group.addoption(
        "--allow-real-db-write",
        action="store_true",
        help="显式允许 pytest 对真实数据库执行写入路径。仅在明确需要重新导入/重置记忆时使用。",
    )


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
    config.addinivalue_line(
        "markers", "converted_data: converted_data 数据集驱动评估"
    )
    config.addinivalue_line(
        "markers", "storage_eval: converted_data 存储链路评估"
    )
    config.addinivalue_line(
        "markers", "retrieval_eval: converted_data 检索链路评估"
    )
    config.addinivalue_line(
        "markers", "assistant_eval: converted_data 端到端回答评估"
    )
    config.addinivalue_line(
        "markers", "personamem_v2: PersonaMem-v2 数据集驱动评估"
    )
