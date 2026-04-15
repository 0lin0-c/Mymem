# 🗄️ Repository 基类：封装通用 CRUD 操作
import logging
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import select, exists as sa_exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tables.base import Base

logger = logging.getLogger(__name__)

# 泛型：表示具体的 ORM 模型类
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """通用 Repository 基类

    提供基础的 CRUD 操作，所有具体 Repository 继承此类，
    复用通用方法的同时实现各自特有的查询逻辑。
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        """
        Args:
            session: SQLAlchemy 异步会话（通常来自 Depends(get_db)）
            model: 对应的 ORM 模型类（如 User, Resource）
        """
        self.session = session
        self.model = model

    async def get_by_id(self, id: str) -> ModelType | None:
        """通过主键 ID 获取单条记录"""
        return await self.session.get(self.model, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """获取所有记录（分页）"""
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelType:
        """创建新记录"""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug(f"创建记录: model={self.model.__name__}, id={instance.id}")
        return instance

    async def update(self, id: str, **kwargs: Any) -> ModelType | None:
        """更新记录（仅更新提供的字段）"""
        instance = await self.get_by_id(id)
        if not instance:
            logger.debug(f"更新记录失败: 不存在, model={self.model.__name__}, id={id}")
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug(f"更新记录: model={self.model.__name__}, id={id}, fields={list(kwargs.keys())}")
        return instance

    async def delete(self, id: str) -> bool:
        """删除记录"""
        instance = await self.get_by_id(id)
        if not instance:
            logger.debug(f"删除记录失败: 不存在, model={self.model.__name__}, id={id}")
            return False
        await self.session.delete(instance)
        await self.session.flush()
        logger.debug(f"删除记录: model={self.model.__name__}, id={id}")
        return True

    async def exists(self, id: str) -> bool:
        """检查记录是否存在"""
        stmt = select(
            sa_exists().where(self.model.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalar()
