# 🔍 记忆去重服务：基于向量相似度和 LLM 判断的去重机制
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession

from tables.resource import Resource
from tables.category import Category
from repositories import ResourceRepository, CategoryRepository
from services.llm.base import BaseLLMProvider
from services.memory.dedup_config import (
    get_threshold_for_category,
    RESOURCE_DEDUP_THRESHOLD,
    cosine_distance_to_similarity,
)

logger = logging.getLogger(__name__)


class DedupAction(Enum):
    """去重操作类型"""
    CREATE = "create"  # 新建记录
    SKIP = "skip"  # 跳过（强化已有记录）
    MERGE = "merge"  # 合并到已有记录
    UPDATE = "update"  # 更新已有记录


@dataclass
class DedupResult:
    """去重检查结果"""
    action: DedupAction
    existing_item: Optional[Resource | Category] = None
    similarity: float = 0.0
    merged_content: Optional[str] = None
    reason: str = ""


class MemoryDeduplicator:
    """记忆去重服务

    提供两级去重：
    1. Resource 级别：综合摘要去重
    2. Category 级别：原子化记忆去重

    去重策略：
    - 相似度 >= skip_threshold: 跳过，强化已有记录
    - 相似度 >= merge_threshold: 调用 LLM 判断 merge/update/create
    - 相似度 < merge_threshold: 新建记录
    """

    def __init__(
        self,
        session: AsyncSession,
        llm: BaseLLMProvider,
    ):
        self.session = session
        self.llm = llm
        self.resource_repo = ResourceRepository(session)
        self.category_repo = CategoryRepository(session)

    async def check_resource_duplicate(
        self,
        user_id: str,
        summary: str,
        vector: list[float],
    ) -> DedupResult:
        """检查 Resource 级别去重

        Args:
            user_id: 用户 ID
            summary: 综合摘要
            vector: 摘要向量（维度由 embedding_dimensions 配置）

        Returns:
            DedupResult: 去重检查结果
        """
        # 使用向量检索找到最相似的 Resource
        similar_resources = await self.resource_repo.search_by_vector(
            user_id=user_id,
            query_vector=vector,
            top_k=1,
            min_importance=1,  # 检查所有资源
        )

        if not similar_resources:
            return DedupResult(action=DedupAction.CREATE)

        existing = similar_resources[0]

        # 计算相似度（通过 Repository 获取 cosine_distance）
        similar_with_distance = await self.resource_repo.get_with_distance(
            user_id=user_id,
            resource_id=existing.id,
            query_vector=vector,
        )

        if similar_with_distance is None:
            return DedupResult(action=DedupAction.CREATE)

        existing, cosine_distance = similar_with_distance
        similarity = cosine_distance_to_similarity(cosine_distance)

        threshold = RESOURCE_DEDUP_THRESHOLD

        # 相似度 >= skip_threshold: 跳过
        if similarity >= threshold.skip_threshold:
            return DedupResult(
                action=DedupAction.SKIP,
                existing_item=existing,
                similarity=similarity,
                reason=f"相似度 {similarity:.3f} >= 跳过阈值 {threshold.skip_threshold}",
            )

        # 相似度 >= merge_threshold: 调用 LLM 判断
        if similarity >= threshold.merge_threshold:
            return await self._llm_judge_resource(
                existing=existing,
                new_summary=summary,
                similarity=similarity,
            )

        # 相似度 < merge_threshold: 新建
        return DedupResult(
            action=DedupAction.CREATE,
            similarity=similarity,
        )

    async def check_category_duplicate(
        self,
        user_id: str,
        category_name: str,
        content: str,
        vector: list[float],
    ) -> DedupResult:
        """检查 Category 级别去重（使用向量检索）

        使用 CategoryRepository.search_by_vector() 进行向量检索，
        避免逐条调用 LLM 生成向量。

        Args:
            user_id: 用户 ID
            category_name: 分类名称
            content: 原子化内容
            vector: 内容向量

        Returns:
            DedupResult: 去重检查结果
        """
        # 使用向量检索找到最相似的 Category（限定在当前分类内）
        similar_items = await self.category_repo.search_by_vector(
            user_id=user_id,
            query_vector=vector,
            category_names=[category_name],  # 限定在当前分类内
            top_k=1,
            min_importance=0,  # 检查所有重要性
        )

        if not similar_items:
            return DedupResult(action=DedupAction.CREATE)

        # search_by_vector 返回 (Category, score) 元组
        best_match, four_factor_score = similar_items[0]

        # 计算相似度（通过 Repository 获取 cosine_distance）
        similar_with_distance = await self.category_repo.get_with_distance(
            user_id=user_id,
            category_id=best_match.id,
            query_vector=vector,
        )

        if similar_with_distance is None:
            return DedupResult(action=DedupAction.CREATE)

        best_match, cosine_distance = similar_with_distance
        best_similarity = cosine_distance_to_similarity(cosine_distance)

        # 获取分类特定阈值
        threshold = get_threshold_for_category(category_name)

        # 相似度 >= skip_threshold: 跳过
        if best_similarity >= threshold.skip_threshold:
            return DedupResult(
                action=DedupAction.SKIP,
                existing_item=best_match,
                similarity=best_similarity,
                reason=f"相似度 {best_similarity:.3f} >= 跳过阈值 {threshold.skip_threshold}",
            )

        # 相似度 >= merge_threshold: 调用 LLM 判断
        if best_similarity >= threshold.merge_threshold:
            return await self._llm_judge_category(
                existing=best_match,
                new_content=content,
                similarity=best_similarity,
                category_name=category_name,
            )

        # 相似度 < merge_threshold: 新建
        return DedupResult(
            action=DedupAction.CREATE,
            similarity=best_similarity,
        )

    async def reinforce_resource(self, resource: Resource) -> Resource:
        """强化已有 Resource（importance_score +1）

        Args:
            resource: 要强化的资源

        Returns:
            更新后的资源
        """
        new_score = min(resource.importance_score + 1, 3)
        return await self.resource_repo.update_importance(resource.id, new_score)

    async def reinforce_category(self, category: Category) -> Category:
        """强化已有 Category（importance_score +1）

        Args:
            category: 要强化的分类项

        Returns:
            更新后的分类项
        """
        new_score = min(category.importance_score + 1, 3)
        return await self.category_repo.update_importance(category.id, new_score)

    async def merge_resource(
        self,
        existing: Resource,
        merged_content: str,
        merged_vector: list[float],
    ) -> Resource:
        """合并内容到已有 Resource

        Args:
            existing: 已有资源
            merged_content: 合并后的内容
            merged_vector: 合并后的向量

        Returns:
            更新后的资源
        """
        return await self.resource_repo.update_content(
            resource_id=existing.id,
            description=merged_content,
            description_vector=merged_vector,
        )

    async def merge_category(
        self,
        existing: Category,
        merged_content: str,
        merged_vector: list[float],
        importance_score: Optional[int] = None,
    ) -> Category:
        """合并内容到已有 Category

        Args:
            existing: 已有分类项
            merged_content: 合并后的内容
            merged_vector: 合并后内容的向量嵌入
            importance_score: 新的重要性分数

        Returns:
            更新后的分类项
        """
        return await self.category_repo.update_content(
            item_id=existing.id,
            content=merged_content,
            content_vector=merged_vector,
            importance_score=importance_score,
        )

    async def _llm_judge_resource(
        self,
        existing: Resource,
        new_summary: str,
        similarity: float,
    ) -> DedupResult:
        """调用 LLM 判断 Resource 的 merge/update/create"""
        prompt = self._build_judge_prompt(
            existing_content=existing.description or "",
            new_content=new_summary,
        )

        try:
            response = await self.llm.generate_chat_response(
                system_prompt="You are a memory management expert, skilled at determining relationships between information.",
                context="",
                user_query=prompt,
            )

            result = self._parse_llm_response(response)

            if result["action"] in (DedupAction.MERGE, DedupAction.UPDATE):
                return DedupResult(
                    action=result["action"],
                    existing_item=existing,
                    similarity=similarity,
                    merged_content=result.get("merged_content"),
                    reason=result.get("reason", ""),
                )

            return DedupResult(
                action=DedupAction.CREATE,
                similarity=similarity,
                reason=result.get("reason", "LLM judged as independent content"),
            )

        except Exception as e:
            logger.error(f"LLM judgment failed: {e}")
            # Default to create on failure
            return DedupResult(
                action=DedupAction.CREATE,
                similarity=similarity,
                reason=f"LLM judgment failed, defaulting to create: {e}",
            )

    async def _llm_judge_category(
        self,
        existing: Category,
        new_content: str,
        similarity: float,
        category_name: str,
    ) -> DedupResult:
        """Call LLM to judge Category merge/update/create"""
        prompt = self._build_judge_prompt(
            existing_content=existing.content,
            new_content=new_content,
        )

        try:
            response = await self.llm.generate_chat_response(
                system_prompt="You are a memory management expert, skilled at determining relationships between information.",
                context="",
                user_query=prompt,
            )

            result = self._parse_llm_response(response)

            if result["action"] in (DedupAction.MERGE, DedupAction.UPDATE):
                return DedupResult(
                    action=result["action"],
                    existing_item=existing,
                    similarity=similarity,
                    merged_content=result.get("merged_content"),
                    reason=result.get("reason", ""),
                )

            return DedupResult(
                action=DedupAction.CREATE,
                similarity=similarity,
                reason=result.get("reason", "LLM judged as independent content"),
            )

        except Exception as e:
            logger.error(f"LLM judgment failed: {e}")
            return DedupResult(
                action=DedupAction.CREATE,
                similarity=similarity,
                reason=f"LLM judgment failed, defaulting to create: {e}",
            )

    def _build_judge_prompt(
        self,
        existing_content: str,
        new_content: str,
    ) -> str:
        """Build LLM judge prompt"""
        return f"""# Existing Memory
{existing_content}

# New Input
{new_content}

# Task
Determine the relationship between the new input and existing memory, and return an action type:

1. **merge**: The new information supplements the existing memory and should be merged into it
2. **update**: The new information corrects/overrides the existing memory
3. **create**: The new information is independent content and should create a new record

# Output Language (Critical)
- **ALWAYS** output merged_content in the same language as the new input.
- If the new input is in Chinese, output merged_content in Chinese.
- If the new input is in English, output merged_content in English.
- This ensures the memory language follows the user's current input language.

# Output Format
Output only JSON without any explanation:
{{
  "action": "merge" | "update" | "create",
  "reason": "Reason for the decision",
  "merged_content": "Merged/updated content (required only for merge/update)"
}}"""

    def _parse_llm_response(self, response: str) -> dict:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)

                action_str = result.get("action", "create").lower()
                action_map = {
                    "merge": DedupAction.MERGE,
                    "update": DedupAction.UPDATE,
                    "create": DedupAction.CREATE,
                }
                result["action"] = action_map.get(action_str, DedupAction.CREATE)

                return result

        except json.JSONDecodeError:
            pass

        return {"action": DedupAction.CREATE, "reason": "解析失败"}

    def _compute_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def _get_embedding(self, text: str) -> Optional[list[float]]:
        """获取文本的向量表示"""
        try:
            return await self.llm.get_embedding(text)
        except Exception as e:
            logger.error(f"获取向量失败: {e}")
            return None
