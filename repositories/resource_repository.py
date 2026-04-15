# 📚 资源 Repository：封装第一轨记忆和向量检索的数据库操作
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from tables.resource import Resource
from tables.resource_category import ResourceCategory
from repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ResourceRepository(BaseRepository[Resource]):
    """第一轨记忆（资源）数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Resource)

    async def get_by_user_id(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Resource]:
        """获取某用户的所有资源"""
        result = await self.session.execute(
            select(Resource)
            .where(Resource.user_id == user_id)
            .order_by(Resource.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_modality(
        self,
        user_id: str,
        modality: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Resource]:
        """按模态筛选资源"""
        result = await self.session.execute(
            select(Resource)
            .where(
                Resource.user_id == user_id,
                Resource.modality == modality,
            )
            .order_by(Resource.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_importance_range(
        self,
        user_id: str,
        min_score: int,
        max_score: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Resource]:
        """按重要性评分范围筛选"""
        result = await self.session.execute(
            select(Resource)
            .where(
                Resource.user_id == user_id,
                Resource.importance_score >= min_score,
                Resource.importance_score <= max_score,
            )
            .order_by(Resource.importance_score.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_high_importance_resources(
        self,
        user_id: str,
        min_importance: int = 5,
        limit: int = 50,
    ) -> list[Resource]:
        """获取高重要性资源（用于检索前的预过滤）"""
        result = await self.session.execute(
            select(Resource)
            .where(
                Resource.user_id == user_id,
                Resource.importance_score >= min_importance,
            )
            .order_by(Resource.importance_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self,
        user_id: str,
        raw_content: str,
        modality: str = "text",
        description: str | None = None,
        description_vector: list[float] | None = None,
        importance_score: int = 5,
        assistant_response: str | None = None,
    ) -> Resource:
        """创建新资源"""
        return await super().create(
            id=str(uuid.uuid4()),
            user_id=user_id,
            raw_content=raw_content,
            modality=modality,
            description=description,
            description_vector=description_vector,
            importance_score=importance_score,
            assistant_response=assistant_response,
        )

    async def search_by_vector(
        self,
        user_id: str,
        query_vector: list[float],
        top_k: int = 5,
        min_importance: int = 3,
        recency_decay_days: int = 60,
    ) -> list[Resource]:
        """向量相似度检索（四因子乘法评分）

        Args:
            user_id: 用户ID
            query_vector: 查询向量（维度由 embedding_dimensions 配置）
            top_k: 返回前 k 条结果
            min_importance: 最低重要性分数
            recency_decay_days: 时间衰减半衰期

        Returns:
            按四因子评分排序的资源列表
        """
        logger.debug(f"Resource 向量检索: user_id={user_id}, top_k={top_k}")
        # 四因子评分: cosine_similarity × log(access_count+1) × exp(-decay) × (importance/5)
        sql = text("""
            SELECT id, user_id, modality, raw_content, description,
                   description_vector, importance_score, created_at, updated_at,
                   assistant_response, access_count,
                   (1 - (description_vector <=> CAST(:query_vector AS vector)))
                   * ln(access_count + 1)
                   * exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400 / :recency_decay_days)
                   * (importance_score / 5.0) AS score
            FROM resources
            WHERE user_id = :user_id
              AND importance_score >= :min_importance
              AND description_vector IS NOT NULL
            ORDER BY score DESC
            LIMIT :top_k
        """)

        result = await self.session.execute(
            sql,
            {
                "query_vector": str(query_vector),
                "user_id": user_id,
                "min_importance": min_importance,
                "top_k": top_k,
                "recency_decay_days": recency_decay_days,
            },
        )
        rows = result.fetchall()

        if not rows:
            logger.debug(f"Resource 向量检索无结果: user_id={user_id}")
            return []

        logger.debug(f"Resource 向量检索结果: 数量={len(rows)}")
        # 重新查询完整对象
        resource_ids = [row[0] for row in rows]
        resources_result = await self.session.execute(
            select(Resource).where(Resource.id.in_(resource_ids))
        )
        resources = list(resources_result.scalars().all())

        # 按分数排序返回
        id_to_resource = {r.id: r for r in resources}
        return [id_to_resource[rid] for rid in resource_ids if rid in id_to_resource]

    async def search_by_vector_in_category(
        self,
        user_id: str,
        category_id: str,
        query_vector: list[float],
        top_k: int = 5,
        recency_decay_days: int = 60,
    ) -> list[tuple[Resource, float]]:
        """在指定分类内进行向量相似度检索（四因子乘法评分）

        Args:
            user_id: 用户ID
            category_id: 分类ID
            query_vector: 查询向量
            top_k: 返回前 k 条结果
            recency_decay_days: 时间衰减半衰期

        Returns:
            (Resource, score) 元组列表
        """
        sql = text("""
            SELECT r.id, r.user_id, r.modality, r.raw_content, r.description,
                   r.description_vector, r.importance_score, r.created_at,
                   r.updated_at, r.assistant_response, r.access_count,
                   (1 - (r.description_vector <=> CAST(:query_vector AS vector)))
                   * ln(r.access_count + 1)
                   * exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - r.updated_at)) / 86400 / :recency_decay_days)
                   * (r.importance_score / 5.0) AS score
            FROM resources r
            INNER JOIN resource_categories rc ON r.id = rc.resource_id
            WHERE r.user_id = :user_id
              AND rc.category_id = :category_id
              AND r.description_vector IS NOT NULL
            ORDER BY score DESC
            LIMIT :top_k
        """)

        result = await self.session.execute(
            sql,
            {
                "query_vector": str(query_vector),
                "user_id": user_id,
                "category_id": category_id,
                "top_k": top_k,
                "recency_decay_days": recency_decay_days,
            },
        )
        rows = result.fetchall()

        if not rows:
            return []

        # 构建结果列表
        results = []
        for row in rows:
            resource = Resource(
                id=row[0],
                user_id=row[1],
                modality=row[2],
                raw_content=row[3],
                description=row[4],
                description_vector=row[5],
                importance_score=row[6],
                created_at=row[7],
                updated_at=row[8],
                assistant_response=row[9],
                access_count=row[10],
            )
            score = row[11]
            results.append((resource, score))

        return results

    async def update_description_vector(
        self,
        resource_id: str,
        description: str,
        description_vector: list[float],
    ) -> Resource | None:
        """更新资源的描述和向量（用于后续 LLM 优化描述后重新向量化）"""
        return await self.update(
            resource_id,
            description=description,
            description_vector=description_vector,
        )

    async def update_importance(self, resource_id: str, importance_score: int) -> Resource | None:
        """更新重要性分数"""
        return await self.update(
            resource_id,
            importance_score=min(max(importance_score, 1), 10),  # 限制在 1-10
        )

    async def update_content(
        self,
        resource_id: str,
        description: str,
        description_vector: list[float],
    ) -> Resource | None:
        """更新内容（合并/覆盖时使用）"""
        return await self.update(
            resource_id,
            description=description,
            description_vector=description_vector,
        )

    async def delete_by_user(self, user_id: str) -> int:
        """删除某用户的所有资源"""
        result = await self.session.execute(
            delete(Resource).where(Resource.user_id == user_id)
        )
        await self.session.flush()
        logger.info(f"删除用户所有资源: user_id={user_id}, count={result.rowcount}")
        return result.rowcount

    async def get_low_importance_resources(
        self,
        user_id: str,
        excluded_category_ids: list[str] = None,
        max_importance: int = 2,
        limit: int = 100,
    ) -> list[Resource]:
        """获取低重要性资源（用于遗忘清理）

        Args:
            user_id: 用户ID
            excluded_category_ids: 排除的分类ID列表（如核心自我、社交关系图谱）
            max_importance: 最大重要性分数
            limit: 返回数量限制
        """
        query = select(Resource).where(
            Resource.user_id == user_id,
            Resource.importance_score <= max_importance,
        )

        # 如果有排除的分类，需要排除这些分类下的资源
        if excluded_category_ids:
            excluded_resource_ids = (
                select(ResourceCategory.resource_id)
                .where(ResourceCategory.category_id.in_(excluded_category_ids))
            )
            query = query.where(Resource.id.not_in(excluded_resource_ids))

        query = query.order_by(Resource.importance_score.asc(), Resource.updated_at.asc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_old_resources(
        self,
        user_id: str,
        excluded_category_ids: list[str] = None,
        days_threshold: int = 180,
        limit: int = 100,
    ) -> list[Resource]:
        """获取过期的资源（用于遗忘清理）"""
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

        query = select(Resource).where(
            Resource.user_id == user_id,
            Resource.updated_at < threshold_date,
        )

        if excluded_category_ids:
            excluded_resource_ids = (
                select(ResourceCategory.resource_id)
                .where(ResourceCategory.category_id.in_(excluded_category_ids))
            )
            query = query.where(Resource.id.not_in(excluded_resource_ids))

        query = query.order_by(Resource.updated_at.asc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_distance(
        self,
        user_id: str,
        resource_id: str,
        query_vector: list[float],
    ) -> tuple[Resource, float] | None:
        """获取资源及其与查询向量的余弦距离

        Args:
            user_id: 用户 ID
            resource_id: 资源 ID
            query_vector: 查询向量

        Returns:
            (Resource, cosine_distance) 元组，不存在返回 None
        """
        sql = text("""
            SELECT id, user_id, modality, raw_content, description,
                   description_vector, importance_score, created_at, updated_at,
                   assistant_response, access_count,
                   (description_vector <=> CAST(:query_vector AS vector)) AS cosine_distance
            FROM resources
            WHERE id = :resource_id AND user_id = :user_id
        """)

        result = await self.session.execute(
            sql,
            {
                "query_vector": str(query_vector),
                "resource_id": resource_id,
                "user_id": user_id,
            },
        )
        row = result.fetchone()

        if row is None:
            return None

        resource = Resource(
            id=row[0],
            user_id=row[1],
            modality=row[2],
            raw_content=row[3],
            description=row[4],
            description_vector=row[5],
            importance_score=row[6],
            created_at=row[7],
            updated_at=row[8],
            assistant_response=row[9],
            access_count=row[10],
        )
        cosine_distance = row[11]

        return resource, cosine_distance
