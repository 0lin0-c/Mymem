# ⚙️ 数据库引擎：初始化 PostgreSQL 异步连接池，提供获取 DB Session 的依赖函数
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings

logger = logging.getLogger(__name__)


# 创建异步引擎
logger.debug(f"初始化数据库引擎: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 生产环境设为 False
    poolclass=NullPool,  # 异步环境使用 NullPool，每次请求新建连接
    connect_args={
        "ssl": None,  # 禁用 SSL（如果远程数据库不支持 SSL）
    },
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖函数

    用于 FastAPI 依赖注入，每个请求都会获得独立的 Session，
    请求结束后自动关闭。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"数据库事务异常，执行回滚: {type(e).__name__}: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
