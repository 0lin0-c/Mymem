# 🔗 记忆来源关联 Repository
import uuid
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from tables.resource_category import ResourceCategory
from tables.resource import Resource
from tables.category import Category
from repositories.base import BaseRepository


class ResourceCategoryRepository(BaseRepository[ResourceCategory]):
    """记忆来源关联数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ResourceCategory)

    async def get_resources_for_category(
        self,
        category_id: str,
        limit: int = 100,
    ) -> List[ResourceCategory]:
        """获取某个原子化记忆的所有来源"""
        result = await self.session.execute(
            select(ResourceCategory)
            .where(ResourceCategory.category_id == category_id)
            .order_by(ResourceCategory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_categories_for_resource(
        self,
        resource_id: str,
        limit: int = 100,
    ) -> List[ResourceCategory]:
        """获取某个对话摘要提取出的所有原子化记忆"""
        result = await self.session.execute(
            select(ResourceCategory)
            .where(ResourceCategory.resource_id == resource_id)
            .order_by(ResourceCategory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_relation(
        self,
        resource_id: str,
        category_id: str,
        relation_type: str = "created",
        note: str | None = None,
    ) -> ResourceCategory:
        """创建关联关系

        Args:
            resource_id: 对话摘要 ID
            category_id: 原子化记忆 ID
            relation_type: 关联类型（created/updated）
            note: 关联说明
        """
        return await super().create(
            id=str(uuid.uuid4()),
            resource_id=resource_id,
            category_id=category_id,
            relation_type=relation_type,
            note=note,
        )

    async def create_relations_batch(
        self,
        resource_id: str,
        category_ids: List[str],
        relation_type: str = "created",
    ) -> List[ResourceCategory]:
        """批量创建关联关系"""
        created = []
        for category_id in category_ids:
            rc = await self.create_relation(
                resource_id=resource_id,
                category_id=category_id,
                relation_type=relation_type,
            )
            created.append(rc)
        return created

    async def delete_by_resource(self, resource_id: str) -> int:
        """删除某个 Resource 的所有关联"""
        result = await self.session.execute(
            delete(ResourceCategory).where(ResourceCategory.resource_id == resource_id)
        )
        await self.session.flush()
        return result.rowcount

    async def delete_by_category(self, category_id: str) -> int:
        """删除某个 Category 的所有关联"""
        result = await self.session.execute(
            delete(ResourceCategory).where(ResourceCategory.category_id == category_id)
        )
        await self.session.flush()
        return result.rowcount

    async def get_relation(
        self,
        resource_id: str,
        category_id: str,
    ) -> ResourceCategory | None:
        """获取特定的关联关系"""
        result = await self.session.execute(
            select(ResourceCategory).where(
                ResourceCategory.resource_id == resource_id,
                ResourceCategory.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()
