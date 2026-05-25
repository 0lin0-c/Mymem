from sqlalchemy.ext.asyncio import AsyncSession

from repositories import CategoryRepository, ResourceRepository


class RetrievalStatsService:
    def __init__(self, session: AsyncSession):
        self.category_repo = CategoryRepository(session)
        self.resource_repo = ResourceRepository(session)

    async def get_stats(self, user_id: str) -> dict:
        category_stats = await self.category_repo.get_category_stats(user_id)
        resources = await self.resource_repo.get_by_user_id(user_id, limit=1000)

        avg_importance = 0.0
        if resources:
            total_importance = sum(resource.importance_score for resource in resources)
            avg_importance = total_importance / len(resources)

        category_distribution = {
            name: {
                "count": stats["count"],
                "avg_importance": stats["avg_importance"],
            }
            for name, stats in category_stats.items()
        }

        return {
            "total_retrievals": len(resources),
            "avg_results_per_query": avg_importance,
            "category_distribution": category_distribution,
            "avg_latency_ms": 0.0,
        }
