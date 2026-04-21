# 🧠 原子化记忆 Repository：封装 Category 表的数据库操作
import logging
import uuid
import math
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from tables.category import Category
from repositories.base import BaseRepository
from services.retrieval.scoring_config import (
    DEFAULT_RETRIEVAL_SCORING_CONFIG,
    RetrievalScoringConfig,
)

logger = logging.getLogger(__name__)


class CategoryRepository(BaseRepository[Category]):
    """原子化记忆数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Category)

    async def get_by_user_id(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Category]:
        """获取某用户的所有原子化记忆"""
        result = await self.session.execute(
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.importance_score.desc(), Category.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_category_name(
        self,
        user_id: str,
        category_name: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Category]:
        """获取某用户某个分类下的所有原子化记忆"""
        result = await self.session.execute(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.category_name == category_name,
            )
            .order_by(Category.importance_score.desc(), Category.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_high_importance_items(
        self,
        user_id: str,
        min_importance: int = 7,
        limit: int = 20,
    ) -> list[Category]:
        """获取高重要性的原子化记忆"""
        result = await self.session.execute(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.importance_score >= min_importance,
            )
            .order_by(Category.importance_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_item(
        self,
        user_id: str,
        category_name: str,
        content: str,
        content_vector: list[float] | None = None,
        importance_score: int = 2,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> Category:
        """创建一条原子化记忆

        Args:
            user_id: 用户ID
            category_name: 分类名称（核心自我/情景时间轴/...）
            content: 原子化的记忆内容
            content_vector: 内容的向量嵌入
            importance_score: importance score (0-3)
        """
        create_data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "category_name": category_name,
            "content": content,
            "content_vector": content_vector,
            "importance_score": min(max(importance_score, 0), 3),
        }
        if created_at is not None:
            create_data["created_at"] = created_at
        if updated_at is not None:
            create_data["updated_at"] = updated_at

        return await super().create(**create_data)

    async def create_items_batch(
        self,
        user_id: str,
        items: List[dict],
    ) -> List[Category]:
        """批量创建原子化记忆

        Args:
            user_id: 用户ID
            items: 原子化信息列表，每个元素包含 category_name, content, content_vector, importance_score

        Returns:
            创建的 Category 列表
        """
        import uuid

        logger.debug(f"批量创建原子化记忆: user_id={user_id}, count={len(items)}")
        # 构建所有实例（不立即 flush）
        instances = []
        for item in items:
            instance = Category(
                id=str(uuid.uuid4()),
                user_id=user_id,
                category_name=item.get("category_name", "Knowledge Base"),
                content=item.get("content", ""),
                content_vector=item.get("content_vector"),
                importance_score=min(max(item.get("importance_score", 2), 0), 3),
            )
            self.session.add(instance)
            instances.append(instance)

        # 一次性 flush 所有实例
        await self.session.flush()

        # 刷新所有实例以获取服务器生成的字段
        for instance in instances:
            await self.session.refresh(instance)

        return instances

    async def update_importance(
        self,
        item_id: str,
        importance_score: int,
    ) -> Category | None:
        """更新重要性分数"""
        return await self.update(
            item_id,
            importance_score=min(max(importance_score, 0), 3),
        )

    async def get_category_stats(self, user_id: str) -> dict:
        """获取各分类的统计信息"""
        result = await self.session.execute(
            select(
                Category.category_name,
                func.count(Category.id).label("count"),
                func.avg(Category.importance_score).label("avg_importance"),
            )
            .where(Category.user_id == user_id)
            .group_by(Category.category_name)
        )
        stats = {}
        for row in result:
            stats[row[0]] = {
                "count": row[1],
                "avg_importance": round(row[2], 2) if row[2] else 0,
            }
        return stats

    async def search_by_content(
        self,
        user_id: str,
        keyword: str,
        limit: int = 10,
    ) -> list[Category]:
        """按内容关键词搜索"""
        result = await self.session.execute(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.content.ilike(f"%{keyword}%"),
            )
            .order_by(Category.importance_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_content(
        self,
        item_id: str,
        content: str,
        content_vector: list[float] | None = None,
        importance_score: int | None = None,
    ) -> Category | None:
        """更新 Category 内容（用于 merge/update）

        Args:
            item_id: 记忆项 ID
            content: 新内容
            content_vector: 新内容的向量嵌入（合并时必须更新）
            importance_score: 新的重要性分数（可选）

        Returns:
            更新后的 Category，不存在返回 None
        """
        update_data = {"content": content}
        if content_vector is not None:
            update_data["content_vector"] = content_vector
        if importance_score is not None:
            update_data["importance_score"] = min(max(importance_score, 0), 3)

        return await self.update(item_id, **update_data)

    async def update_dynamic_category_names(
        self,
        user_id: str,
        old_names: list[str],
        new_names: list[str],
    ) -> int:
        """更新动态分类名称

        Args:
            user_id: 用户 ID
            old_names: 旧的分类名称列表
            new_names: 新的分类名称列表

        Returns:
            更新的记录数
        """
        from sqlalchemy import update

        updated_count = 0
        for old_name, new_name in zip(old_names, new_names):
            if old_name != new_name:
                result = await self.session.execute(
                    update(Category)
                    .where(
                        Category.user_id == user_id,
                        Category.category_name == old_name,
                    )
                    .values(category_name=new_name)
                )
                updated_count += result.rowcount

        return updated_count

    async def search_by_vector(
        self,
        user_id: str,
        query_vector: list[float],
        category_names: list[str] | None = None,
        top_k: int = 5,
        min_importance: int = 0,
        recency_decay_days: int = 60,
        scoring_config: RetrievalScoringConfig | None = None,
    ) -> list[tuple[Category, float]]:
        """向量相似度检索（四因子乘法评分）

        Args:
            user_id: 用户ID
            query_vector: 查询向量（维度由 embedding_dimensions 配置）
            category_names: 限定分类名称列表（None 表示所有分类）
            top_k: 返回前 k 条结果
            min_importance: 最低重要性分数
            recency_decay_days: 时间衰减半衰期

        Returns:
            (Category, score) 元组列表，按四因子评分降序排序
        """
        logger.debug(f"Category 向量检索: user_id={user_id}, categories={category_names}, top_k={top_k}")
        scoring_config = scoring_config or DEFAULT_RETRIEVAL_SCORING_CONFIG
        # 构建基础过滤条件
        where_clauses = [
            "user_id = :user_id",
            "importance_score >= :min_importance",
            "content_vector IS NOT NULL",
        ]
        params = {
            "query_vector": str(query_vector),
            "user_id": user_id,
            "min_importance": min_importance,
            **scoring_config.sql_params(),
        }

        if category_names:
            where_clauses.append("category_name = ANY(:category_names)")
            params["category_names"] = category_names

        # 四因子评分 SQL
        # score = cosine_similarity × log(access_count+2) × exp(-0.693 × days_ago / 60) × small importance boost
        # 注: +2 而非 +1，确保 access_count=0 时评分不为0（ln(2)≈0.693）
        sql = text(f"""
            SELECT id, user_id, category_name, content, content_vector,
                   importance_score, access_count, created_at, updated_at,
                   power(GREATEST((1 - (content_vector <=> CAST(:query_vector AS vector))), 0), :similarity_power)
                   * power(ln(access_count + 2), :access_power)
                   * power(exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400 / :recency_decay_days), :recency_power)
                   * power((0.7 + (importance_score / 10.0)), :importance_power) AS score
            FROM categories
            WHERE {' AND '.join(where_clauses)}
            ORDER BY score DESC
            LIMIT :top_k
        """)
        params["top_k"] = top_k

        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        if not rows:
            logger.debug(f"Category 向量检索无结果: user_id={user_id}")
            return []

        logger.debug(f"Category 向量检索结果: 数量={len(rows)}")
        # 构建 (Category, score) 元组列表
        results = []
        for row in rows:
            category = Category(
                id=row[0],
                user_id=row[1],
                category_name=row[2],
                content=row[3],
                content_vector=row[4],
                importance_score=row[5],
                access_count=row[6],
                created_at=row[7],
                updated_at=row[8],
            )
            score = row[9]
            results.append((category, score))

        return results

    async def get_with_distance(
        self,
        user_id: str,
        category_id: str,
        query_vector: list[float],
    ) -> tuple[Category, float] | None:
        """获取分类项及其与查询向量的余弦距离

        Args:
            user_id: 用户 ID
            category_id: 分类 ID
            query_vector: 查询向量

        Returns:
            (Category, cosine_distance) 元组，不存在返回 None
        """
        sql = text("""
            SELECT id, user_id, category_name, content, content_vector,
                   importance_score, access_count, created_at, updated_at,
                   (content_vector <=> CAST(:query_vector AS vector)) AS cosine_distance
            FROM categories
            WHERE id = :category_id AND user_id = :user_id
        """)

        result = await self.session.execute(
            sql,
            {
                "query_vector": str(query_vector),
                "category_id": category_id,
                "user_id": user_id,
            },
        )
        row = result.fetchone()

        if row is None:
            return None

        category = Category(
            id=row[0],
            user_id=row[1],
            category_name=row[2],
            content=row[3],
            content_vector=row[4],
            importance_score=row[5],
            access_count=row[6],
            created_at=row[7],
            updated_at=row[8],
        )
        cosine_distance = row[9]

        return category, cosine_distance
