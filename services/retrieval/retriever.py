# 🔍 记忆检索服务：LLM 分类判断 + 双层检索
import logging
from typing import List, Dict, Any, Optional
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from services.llm.base import BaseLLMProvider
from services.retrieval.vector_strategy import VectorStrategy
from services.memory.dedup_config import cosine_distance_to_similarity
from repositories import CategoryRepository, ResourceRepository
from tables import Resource, Category

logger = logging.getLogger(__name__)

# 四因子评分阈值（详见 retrieval-pipeline/config/scoring.md）
FOUR_FACTOR_THRESHOLD_HIGH = 0.6   # 降级策略：足够
FOUR_FACTOR_THRESHOLD_MEDIUM = 0.2
FOUR_FACTOR_THRESHOLD_LOW = 0.1    # 过滤阈值

# 四因子评分参数
RECENCY_DECAY_DAYS = 60  # 时间衰减半衰期（天）


class MemoryRetriever:
    """记忆检索服务

    检索流程（双层检索架构）：
    1. LLM 分类判断：分析 query 属于哪些分类
    2. Category 层向量检索：在 LLM 指定的类别中检索 Category 表
    3. LLM 充足性判断：判断 Category 结果是否足够回答问题
    4. Resource 层向量检索：如果不足，根据 Category 关联检索 Resource
    5. 结果合并与上下文构建
    """

    def __init__(
        self,
        session: AsyncSession,
        llm: BaseLLMProvider,
    ):
        self.session = session
        self.llm = llm
        self.category_repo = CategoryRepository(session)
        self.resource_repo = ResourceRepository(session)
        self.vector_strategy = VectorStrategy(session, llm)

    async def retrieve(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        use_llm_classification: bool = True,
    ) -> List[Dict[str, Any]]:
        """检索相关记忆

        Args:
            user_id: 用户 ID
            query: 用户查询
            top_k: 返回数量
            use_llm_classification: 是否使用 LLM 分类判断

        Returns:
            检索结果列表，每项包含 resource, score, strategy, category
        """
        results = []

        # Step 1: LLM 分类判断
        categories = []
        if use_llm_classification:
            categories = await self._classify_query(user_id, query)
            logger.info(f"LLM 分类结果: {categories}")

        # Step 2: Category 层向量检索（第一层）
        category_results = []
        if categories:
            category_results = await self._search_category_layer(
                user_id=user_id,
                categories=categories,
                query=query,
                top_k=top_k,
            )
            logger.info(f"Category 层检索结果: {len(category_results)} 条")

        # Step 3: LLM 充足性判断
        is_sufficient = await self._check_sufficiency(query, category_results)
        logger.info(f"充足性判断结果: {'足够' if is_sufficient else '不足'}")

        if is_sufficient:
            # Category 结果足够，直接构建上下文
            results = self._format_category_results(category_results)
        else:
            # Step 4: Resource 层向量检索（第二层）
            if categories:
                resource_results = await self._search_resource_layer(
                    user_id=user_id,
                    categories=categories,
                    query=query,
                    top_k=top_k,
                )
                logger.info(f"Resource 层检索结果: {len(resource_results)} 条")
                results = self._merge_results(category_results, resource_results)
            else:
                # 无分类，使用向量全局检索作为兜底
                results = await self.vector_strategy.search(
                    user_id=user_id,
                    query=query,
                    top_k=top_k,
                )

        # Step 5: 去重、排序、阈值过滤
        results = self._deduplicate_and_rank(results)
        results = self._filter_by_threshold(results)

        # Step 6: 增加访问计数
        await self._increment_access_counts(results)

        return results[:top_k]

    async def _classify_query(self, user_id: str, query: str) -> List[str]:
        """使用 LLM 判断查询属于哪些分类

        Args:
            user_id: 用户 ID
            query: 用户查询

        Returns:
            相关分类名称列表
        """
        # 动态获取用户的分类列表
        user_categories = await self._get_user_categories(user_id)
        if not user_categories:
            logger.warning(f"用户 {user_id} 没有任何分类")
            return []

        prompt = self._build_classification_prompt(query, user_categories)

        try:
            response = await self.llm.generate_chat_response(
                system_prompt="你是一个分类专家，擅长判断用户问题属于哪个记忆分类。",
                context="",
                user_query=prompt,
            )

            # 解析 LLM 返回的分类
            categories = self._parse_classification_response(response, user_categories)
            return categories

        except Exception as e:
            logger.error(f"LLM 分类判断失败: {e}")
            return []

    async def _get_user_categories(self, user_id: str) -> List[str]:
        """获取用户的所有分类名称

        Args:
            user_id: 用户 ID

        Returns:
            分类名称列表
        """
        # 从 CategoryRepository 获取用户的分类统计
        stats = await self.category_repo.get_category_stats(user_id)
        return list(stats.keys()) if stats else []

    def _build_classification_prompt(self, query: str, available_categories: List[str]) -> str:
        """构建分类判断 prompt

        Args:
            query: 用户查询
            available_categories: 可用的分类列表

        Returns:
            构建的 prompt
        """
        categories_text = "\n".join(available_categories)

        return f"""# Role
你是一个记忆分类专家。根据用户查询，判断需要检索哪些类别的记忆。

# 用户查询
{query}

# 可用分类
{categories_text}

# 判断规则
1. 只返回与查询直接相关的分类
2. 数量不限，但不要过度泛化
3. 如果查询明确指向某个领域，只返回该领域
4. 如果查询模糊，可以返回多个相关分类

# 输出格式
返回 JSON 数组：
["分类名1", "分类名2", ...]"""

    def _parse_classification_response(self, response: str, valid_categories: List[str]) -> List[str]:
        """解析分类结果

        Args:
            response: LLM 返回的响应
            valid_categories: 有效的分类列表

        Returns:
            解析出的分类名称列表
        """
        import json

        try:
            # 尝试提取 JSON 数组
            start = response.find("[")
            end = response.rfind("]") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                categories = json.loads(json_str)

                # 过滤有效分类
                valid_categories_set = set(valid_categories)
                return [
                    cat for cat in categories
                    if cat in valid_categories_set
                ]

        except (json.JSONDecodeError, TypeError):
            pass

        return []

    async def _search_category_layer(
        self,
        user_id: str,
        categories: List[str],
        query: str,
        top_k: int = 5,
        min_importance: int = 3,
    ) -> List[Dict[str, Any]]:
        """Category 层向量检索（第一层）

        在 LLM 指定的类别中检索 Category 表，
        使用 content_vector 相似度 + 四因子评分排序。

        Args:
            user_id: 用户 ID
            categories: 分类名称列表
            query: 查询文本
            top_k: 返回数量
            min_importance: 最低重要性过滤

        Returns:
            检索结果列表，每项包含 category, score
        """
        if not categories:
            return []

        # Step 1: 获取查询向量
        try:
            query_vector = await self.llm.get_embedding(query)
        except Exception as e:
            logger.error(f"获取查询向量失败: {e}")
            return []

        # Step 2: 使用 CategoryRepository 的向量检索方法（返回带分数的元组）
        category_results = await self.category_repo.search_by_vector(
            user_id=user_id,
            query_vector=query_vector,
            category_names=categories,
            top_k=top_k,
            min_importance=min_importance,
            recency_decay_days=RECENCY_DECAY_DAYS,
        )

        # Step 3: 格式化结果（直接使用 Repository 返回的四因子评分）
        results = []
        for category, score in category_results:
            results.append({
                "category": category,
                "score": score,
                "strategy": "category_vector",
            })

        return results

    async def _check_sufficiency(
        self,
        query: str,
        category_results: List[Dict[str, Any]],
    ) -> bool:
        """LLM 充足性判断

        判断 Category 层检索结果是否足够回答用户问题。

        Args:
            query: 用户查询
            category_results: Category 层检索结果

        Returns:
            True 表示足够，False 表示不足
        """
        # 无结果，直接判定不足
        if not category_results:
            return False

        # 构建充足性判断 prompt
        memories_text = "\n".join([
            f"- [{r['category'].category_name}] {r['category'].content}"
            for r in category_results
        ])

        prompt = f"""# 用户问题
{query}

# 检索到的记忆片段
{memories_text}

# 判断规则
1. 记忆片段提供了回答问题所需的全部关键信息 → 足够
2. 记忆片段信息模糊、缺少细节、需要更多上下文 → 不足
3. 优先判断为"足够"，避免过度检索

# 输出格式
返回 JSON：
{{"sufficient": true/false, "reason": "简要说明判断理由"}}"""

        try:
            response = await self.llm.generate_chat_response(
                system_prompt="你是一个判断专家，擅长判断已有信息是否足够回答问题。",
                context="",
                user_query=prompt,
            )

            # 解析结果
            import json
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(response[start:end])
                return result.get("sufficient", False)

        except Exception as e:
            logger.warning(f"LLM 充足性判断失败: {e}，使用降级策略")
            # 降级策略：基于四因子评分阈值
            best_score = max(r.get("score", 0) for r in category_results) if category_results else 0
            if best_score >= FOUR_FACTOR_THRESHOLD_HIGH:
                return True
            if len(category_results) >= 3:
                return True
            return False

        return False

    async def _search_resource_layer(
        self,
        user_id: str,
        categories: List[str],
        query: str,
        top_k: int = 5,
        min_importance: int = 3,
    ) -> List[Dict[str, Any]]:
        """Resource 层向量检索（第二层）

        根据已检索 Category 关联的 Resource，
        按 description_vector 相似度 + 四因子评分排序。

        Args:
            user_id: 用户 ID
            categories: 分类名称列表
            query: 查询文本
            top_k: 返回数量
            min_importance: 最低重要性过滤

        Returns:
            检索结果列表
        """
        if not categories:
            return []

        # Step 1: 获取查询向量
        try:
            query_vector = await self.llm.get_embedding(query)
        except Exception as e:
            logger.error(f"获取查询向量失败: {e}")
            return []

        # Step 2: 执行四因子评分向量检索 SQL
        sql = text("""
            SELECT
                r.id, r.user_id, r.modality, r.raw_content, r.description,
                r.description_vector, r.importance_score, r.created_at,
                r.assistant_response, r.access_count, r.updated_at,
                (1 - (r.description_vector <=> CAST(:query_vector AS vector)))
                * ln(r.access_count + 1)
                * exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - r.updated_at)) / 86400 / :recency_decay_days)
                * (r.importance_score / 5.0) AS score
            FROM resources r
            JOIN resource_categories rc ON r.id = rc.resource_id
            JOIN categories c ON rc.category_id = c.id
            WHERE r.user_id = :user_id
              AND c.category_name = ANY(:target_categories)
              AND r.importance_score >= :min_importance
              AND r.description_vector IS NOT NULL
            ORDER BY score DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            sql,
            {
                "query_vector": str(query_vector),
                "user_id": user_id,
                "target_categories": categories,
                "min_importance": min_importance,
                "recency_decay_days": RECENCY_DECAY_DAYS,
                "limit": top_k * 2,  # 多取一些用于去重
            },
        )
        rows = result.fetchall()

        if not rows:
            return []

        # Step 3: 组装结果（去重）
        results = []
        seen_resource_ids = set()

        for row in rows:
            resource_id = row[0]
            if resource_id in seen_resource_ids:
                continue
            seen_resource_ids.add(resource_id)

            score = row[11]  # 四因子评分

            # 创建 Resource 对象
            resource = Resource(
                id=resource_id,
                user_id=row[1],
                modality=row[2],
                raw_content=row[3],
                description=row[4],
                description_vector=row[5],
                importance_score=row[6],
                created_at=row[7],
                assistant_response=row[8],
                access_count=row[9],
                updated_at=row[10],
            )

            results.append({
                "resource": resource,
                "score": score,
                "strategy": "resource_vector",
            })

        return results

    def _format_category_results(
        self,
        category_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """将 Category 结果格式化为统一格式

        Args:
            category_results: Category 层检索结果

        Returns:
            格式化后的结果列表
        """
        results = []
        for item in category_results:
            category = item.get("category")
            score = item.get("score", 0)

            # Category 结果可能没有关联的 Resource
            results.append({
                "resource": None,
                "category": category,
                "score": score,
                "strategy": "category_vector",
            })

        return results

    def _merge_results(
        self,
        category_results: List[Dict[str, Any]],
        resource_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """合并 Category 和 Resource 层检索结果

        Args:
            category_results: Category 层检索结果
            resource_results: Resource 层检索结果

        Returns:
            合并后的结果列表
        """
        merged = list(category_results)
        merged.extend(resource_results)
        return merged

    def _deduplicate_and_rank(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """去重并排序

        按 resource_id 去重，保留分数最高的
        Category 结果（无 resource）保留在最终结果中
        """
        seen_resources = {}
        category_only_results = []

        for result in results:
            resource = result.get("resource")

            if resource:
                # 有 Resource 的结果按 resource_id 去重
                if resource.id not in seen_resources or result["score"] > seen_resources[resource.id]["score"]:
                    seen_resources[resource.id] = result
            else:
                # 只有 Category 的结果保留
                category_only_results.append(result)

        # 合并并按分数降序排序
        all_results = list(seen_resources.values()) + category_only_results
        sorted_results = sorted(all_results, key=lambda x: x["score"], reverse=True)
        return sorted_results

    def _filter_by_threshold(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """按阈值过滤

        四因子评分阈值：
        - < 0.1: 过滤掉
        - 重要性 < 3: 过滤掉
        """
        filtered = []
        for result in results:
            score = result.get("score", 0)
            resource = result.get("resource")
            category = result.get("category")

            # 四因子评分阈值过滤
            if score < FOUR_FACTOR_THRESHOLD_LOW:
                continue

            # 重要性阈值过滤（针对 Resource）
            if resource and resource.importance_score < 3:
                continue

            # 重要性阈值过滤（针对 Category）
            if category and category.importance_score < 3:
                continue

            filtered.append(result)

        return filtered

    async def _increment_access_counts(
        self,
        results: List[Dict[str, Any]],
    ) -> None:
        """增加检索结果的访问计数

        用于四因子评分中的 access_count 因子。

        Args:
            results: 检索结果列表
        """
        logger.debug(f"增加访问计数: results_count={len(results)}")
        for result in results:
            resource = result.get("resource")
            category = result.get("category")

            # 增加 Resource 访问计数
            if resource:
                try:
                    await self.resource_repo.update(
                        resource.id,
                        access_count=(resource.access_count or 0) + 1,
                    )
                except Exception as e:
                    logger.warning(f"增加 Resource 访问计数失败: {e}")

            # 增加 Category 访问计数
            if category:
                try:
                    await self.category_repo.update(
                        category.id,
                        access_count=(category.access_count or 0) + 1,
                    )
                except Exception as e:
                    logger.warning(f"增加 Category 访问计数失败: {e}")

    async def build_context_from_results(
        self,
        results: List[Dict[str, Any]],
        max_tokens: int = 2000,
    ) -> str:
        """从已有检索结果构建上下文字符串

        避免重复调用 retrieve()，直接用已有结果格式化。
        使用 token 计数控制上下文总长度。

        Args:
            results: retrieve() 返回的检索结果列表
            max_tokens: 最大 token 数

        Returns:
            格式化的上下文字符串
        """
        if not results:
            return ""

        context_parts = []
        current_tokens = 0

        for result in results:
            resource = result.get("resource")
            category = result.get("category")
            score = result.get("score", 0)

            # 优先使用 Resource 的描述，其次使用 Category 的内容
            if resource and resource.description:
                if category:
                    part = f"[{category.category_name}] {resource.description}"
                else:
                    part = f"[记忆] {resource.description}"
            elif category and category.content:
                part = f"[{category.category_name}] {category.content}"
            else:
                continue

            part += f" (相关性: {score:.2f})"

            # Token 计数（降级策略：count_tokens 失败时用 len // 4 估算）
            try:
                part_tokens = await self.llm.count_tokens(part)
            except Exception:
                part_tokens = len(part) // 4

            if current_tokens + part_tokens > max_tokens:
                break

            context_parts.append(part)
            current_tokens += part_tokens

        return "\n".join(context_parts)

    async def build_context(
        self,
        user_id: str,
        query: str,
        max_tokens: int = 2000,
    ) -> str:
        """构建检索上下文

        将检索结果格式化为上下文字符串，用于 LLM prompt

        Args:
            user_id: 用户 ID
            query: 用户查询
            max_tokens: 最大 token 数

        Returns:
            格式化的上下文字符串
        """
        results = await self.retrieve(user_id, query)
        return await self.build_context_from_results(results, max_tokens=max_tokens)
