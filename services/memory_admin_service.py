from sqlalchemy.ext.asyncio import AsyncSession

from repositories import CategoryRepository, ResourceCategoryRepository, ResourceRepository


class MemoryAdminService:
    def __init__(self, session: AsyncSession):
        self.category_repo = CategoryRepository(session)
        self.resource_repo = ResourceRepository(session)
        self.resource_category_repo = ResourceCategoryRepository(session)
        self.session = session

    async def get_atomic_items(
        self,
        user_id: str,
        category_name: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if category_name:
            items = await self.category_repo.get_by_category_name(
                user_id,
                category_name,
                limit=limit,
            )
        else:
            items = await self.category_repo.get_by_user_id(user_id, limit=limit)

        return [
            {
                "id": item.id,
                "category_name": item.category_name,
                "content": item.content,
                "importance_score": item.importance_score,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]

    async def get_category_stats(self, user_id: str) -> dict:
        return await self.category_repo.get_category_stats(user_id)

    async def get_resources(self, user_id: str, limit: int = 20) -> list[dict]:
        resources = await self.resource_repo.get_by_user_id(user_id, limit=limit)
        return [
            {
                "id": resource.id,
                "modality": resource.modality,
                "description": resource.description,
                "assistant_response": resource.assistant_response,
                "importance_score": resource.importance_score,
                "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
                "created_at": resource.created_at.isoformat() if resource.created_at else None,
            }
            for resource in resources
        ]

    async def get_resource_detail(self, resource_id: str, user_id: str) -> dict | None:
        resource = await self.resource_repo.get_by_id(resource_id)
        if not resource or resource.user_id != user_id:
            return None

        relations = await self.resource_category_repo.get_categories_for_resource(resource_id)
        atomic_items = []
        for relation in relations:
            item = await self.category_repo.get_by_id(relation.category_id)
            if item:
                atomic_items.append(item)

        return {
            "id": resource.id,
            "modality": resource.modality,
            "raw_content": resource.raw_content,
            "description": resource.description,
            "assistant_response": resource.assistant_response,
            "importance_score": resource.importance_score,
            "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
            "created_at": resource.created_at.isoformat() if resource.created_at else None,
            "atomic_items": [
                {
                    "id": item.id,
                    "category_name": item.category_name,
                    "content": item.content,
                    "importance_score": item.importance_score,
                }
                for item in atomic_items
            ],
        }

    async def delete_resource(self, resource_id: str, user_id: str) -> bool:
        resource = await self.resource_repo.get_by_id(resource_id)
        if not resource or resource.user_id != user_id:
            return False

        await self.resource_category_repo.delete_by_resource(resource_id)
        await self.resource_repo.delete(resource_id)
        await self.session.commit()
        return True

    async def delete_atomic_item(self, item_id: str, user_id: str) -> bool:
        item = await self.category_repo.get_by_id(item_id)
        if not item or item.user_id != user_id:
            return False

        await self.category_repo.delete(item_id)
        await self.session.commit()
        return True

    async def update_resource(
        self,
        resource_id: str,
        user_id: str,
        description: str,
        importance_score: int | None = None,
    ) -> bool:
        resource = await self.resource_repo.get_by_id(resource_id)
        if not resource or resource.user_id != user_id:
            return False

        update_data = {"description": description}
        if importance_score is not None:
            update_data["importance_score"] = importance_score

        await self.resource_repo.update(resource_id, **update_data)
        await self.session.commit()
        return True

    async def update_atomic_item(
        self,
        item_id: str,
        user_id: str,
        content: str,
        importance_score: int | None = None,
    ) -> bool:
        item = await self.category_repo.get_by_id(item_id)
        if not item or item.user_id != user_id:
            return False

        update_data = {"content": content}
        if importance_score is not None:
            update_data["importance_score"] = importance_score

        await self.category_repo.update(item_id, **update_data)
        await self.session.commit()
        return True
