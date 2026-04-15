# 🔢 向量深度检索策略（第二轨）
import logging
from typing import List

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tables import Resource
from services.retrieval.base import RetrievalStrategy
from services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# 四因子评分参数
RECENCY_DECAY_DAYS = 60  # 时间衰减半衰期（天）


class VectorStrategy(RetrievalStrategy):
    """基于向量相似度的深度检索

    策略：
    1. 将用户 query 转为向量
    2. 使用四因子评分公式：cosine_similarity × log(access_count+1) × exp(-decay) × (importance/5)
    3. 按评分降序返回 Top-K
    """

    def __init__(self, session: AsyncSession, llm: BaseLLMProvider):
        super().__init__(session)
        self.llm = llm

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        min_importance: int = 3,
    ) -> List[dict]:
        """
        通过向量相似度深度检索记忆

        使用四因子乘法评分：
        score = cosine_similarity × log(access_count+1) × exp(-0.693 × days_ago / 60) × (importance_score / 5)

        适用于：需要语义理解的模糊查询
        """
        # Step 1: 将 query 转为向量
        embedding = await self.llm.get_embedding(query)

        # Step 2: 向量检索（四因子评分）
        sql = text("""
            SELECT id, user_id, modality, raw_content, description,
                   description_vector, importance_score, created_at, assistant_response,
                   access_count, updated_at,
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
                "query_vector": str(embedding),
                "user_id": user_id,
                "min_importance": min_importance,
                "top_k": top_k,
                "recency_decay_days": RECENCY_DECAY_DAYS,
            },
        )
        rows = result.fetchall()

        if not rows:
            return []

        # Step 3: 查询完整对象并组装结果
        resource_ids = [row[0] for row in rows]
        resources_result = await self.session.execute(
            select(Resource).where(Resource.id.in_(resource_ids))
        )
        resources = list(resources_result.scalars().all())
        id_to_resource = {r.id: r for r in resources}

        results = []
        for row in rows:
            resource = id_to_resource.get(row[0])
            if resource:
                results.append({
                    "resource": resource,
                    "score": row[11],  # 四因子评分
                    "strategy": "vector",
                })

        # 按分数排序（SQL 已排序，这里确保顺序）
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    async def is_needed(self, context: str) -> bool:
        """
        当 Category 策略结果不足时使用
        """
        return True  # 可根据 context 长度等条件调整
