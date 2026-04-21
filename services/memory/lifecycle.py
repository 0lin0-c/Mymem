# 🔄 记忆生命周期服务：遗忘和统计
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from repositories import (
    CategoryRepository,
    ResourceRepository,
)
from services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


# Fixed category names excluded from forgetting mechanism
FORGETTING_EXCLUDED_CATEGORIES = ["Core Self", "Social Graph"]


class MemoryLifecycle:
    """记忆生命周期管理服务

    职责：
    1. 记忆遗忘（排除核心自我、社交关系图谱）
    2. 重要性衰减（带访问加成）
    3. 统计信息
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

    # ========== 遗忘机制 ==========

    async def calculate_effective_importance(
        self,
        item_id: str,
        is_resource: bool = True,
    ) -> float:
        """计算有效重要性（考虑衰减和访问加成）

        使用艾宾浩斯遗忘曲线的改进版本：
        EffectiveScore = Importance × e^(-Days / (Importance × 5)) × (1 + log(AccessCount + 1))

        Args:
            item_id: 记忆项 ID
            is_resource: 是否是 Resource

        Returns:
            有效重要性分数
        """
        if is_resource:
            item = await self.resource_repo.get_by_id(item_id)
        else:
            item = await self.category_repo.get_by_id(item_id)

        if not item:
            return 0.0

        # 计算距上次更新的天数
        if item.updated_at:
            days_since_update = (datetime.now(timezone.utc) - item.updated_at).days
        else:
            days_since_update = (datetime.now(timezone.utc) - item.created_at).days

        importance = max(item.importance_score, 0)
        access_count = item.access_count or 0

        # 时间衰减因子：e^(-Days / (Importance × 5))
        # 半衰期与重要性正相关
        decay_base = max(importance, 1)
        decay_factor = math.exp(-days_since_update / (decay_base * 5))

        # 访问加成因子：(1 + log(AccessCount + 1))
        # 对数增长，防止过度膨胀
        access_bonus = 1 + math.log(access_count + 1)

        # 有效重要性
        effective_importance = importance * decay_factor * access_bonus

        return effective_importance

    async def decay_importance(
        self,
        user_id: str,
    ) -> Dict[str, int]:
        """对用户所有记忆执行重要性衰减

        注意：核心自我和社交关系图谱的原子化信息不参与衰减

        Returns:
            受影响的记忆数量 {"resources": n, "categories": m}
        """
        # 获取所有 Resource
        resources = await self.resource_repo.get_by_user_id(user_id, limit=1000)
        resource_updated = 0

        for resource in resources:
            effective_importance = await self.calculate_effective_importance(
                resource.id, is_resource=True
            )

            if effective_importance < resource.importance_score - 0.5:
                new_score = max(int(effective_importance), 0)
                await self.resource_repo.update_importance(resource.id, new_score)
                resource_updated += 1

        # 获取所有 Category（原子化信息）
        categories = await self.category_repo.get_by_user_id(user_id, limit=1000)
        category_updated = 0

        for category in categories:
            # 跳过不参与遗忘的分类
            if category.category_name in FORGETTING_EXCLUDED_CATEGORIES:
                continue

            effective_importance = await self.calculate_effective_importance(
                category.id, is_resource=False
            )

            if effective_importance < category.importance_score - 0.5:
                new_score = max(int(effective_importance), 0)
                await self.category_repo.update_importance(category.id, new_score)
                category_updated += 1

        logger.info(
            f"重要性衰减完成: user_id={user_id}, "
            f"resources={resource_updated}, categories={category_updated}"
        )
        return {"resources": resource_updated, "categories": category_updated}

    async def forget_low_importance(
        self,
        user_id: str,
        threshold: float = 0.5,
        min_days: int = 30,
    ) -> Dict[str, int]:
        """删除低重要性记忆

        遗忘规则：
        - 有效重要性 < 1：标记为"待遗忘"
        - 有效重要性 < 0.5 且超过 min_days 天未访问：彻底删除
        - 核心自我和社交关系图谱不参与遗忘

        Args:
            user_id: 用户 ID
            threshold: 有效重要性阈值
            min_days: 最小未访问天数

        Returns:
            删除的记忆数量 {"resources": n, "categories": m}
        """
        # 删除低重要性的 Resource
        resources = await self.resource_repo.get_by_user_id(user_id, limit=1000)
        resource_deleted = 0

        for resource in resources:
            effective_importance = await self.calculate_effective_importance(
                resource.id, is_resource=True
            )

            # 计算距最后更新的天数
            if resource.updated_at:
                days = (datetime.now(timezone.utc) - resource.updated_at).days
            else:
                days = (datetime.now(timezone.utc) - resource.created_at).days

            # 满足删除条件
            if effective_importance < threshold and days > min_days:
                await self.resource_repo.delete(resource.id)
                resource_deleted += 1

        # 删除低重要性的原子化信息（Category 表）
        categories = await self.category_repo.get_by_user_id(user_id, limit=1000)
        category_deleted = 0

        for category in categories:
            # 跳过不参与遗忘的分类
            if category.category_name in FORGETTING_EXCLUDED_CATEGORIES:
                continue

            effective_importance = await self.calculate_effective_importance(
                category.id, is_resource=False
            )

            # 计算距最后更新的天数
            if category.updated_at:
                days = (datetime.now(timezone.utc) - category.updated_at).days
            else:
                days = (datetime.now(timezone.utc) - category.created_at).days

            # 满足删除条件
            if effective_importance < threshold and days > min_days:
                await self.category_repo.delete(category.id)
                category_deleted += 1

        logger.info(
            f"遗忘清理完成: user_id={user_id}, "
            f"resources={resource_deleted}, categories={category_deleted}"
        )
        return {"resources": resource_deleted, "categories": category_deleted}

    async def mark_for_forgetting(
        self,
        user_id: str,
    ) -> Dict[str, int]:
        """标记待遗忘的记忆（有效重要性 < 1）

        注意：核心自我和社交关系图谱不参与

        Args:
            user_id: 用户 ID

        Returns:
            标记的记忆数量
        """
        resources = await self.resource_repo.get_by_user_id(user_id, limit=1000)
        resource_marked = 0

        for resource in resources:
            effective_importance = await self.calculate_effective_importance(
                resource.id, is_resource=True
            )

            # 有效重要性 < 1 标记为待遗忘
            # 这里通过将 importance_score 设为 1 来标记
            if effective_importance < 1 and resource.importance_score > 0:
                await self.resource_repo.update_importance(resource.id, 0)
                resource_marked += 1

        categories = await self.category_repo.get_by_user_id(user_id, limit=1000)
        category_marked = 0

        for category in categories:
            if category.category_name in FORGETTING_EXCLUDED_CATEGORIES:
                continue

            effective_importance = await self.calculate_effective_importance(
                category.id, is_resource=False
            )

            if effective_importance < 1 and category.importance_score > 0:
                await self.category_repo.update_importance(category.id, 0)
                category_marked += 1

        logger.info(
            f"待遗忘标记完成: user_id={user_id}, "
            f"resources={resource_marked}, categories={category_marked}"
        )
        return {"resources": resource_marked, "categories": category_marked}

    # ========== 访问计数 ==========

    async def increment_access_count(
        self,
        item_id: str,
        is_resource: bool = True,
    ) -> bool:
        """增加访问计数（检索时调用）

        Args:
            item_id: 记忆项 ID
            is_resource: 是否是 Resource

        Returns:
            是否成功
        """
        try:
            if is_resource:
                resource = await self.resource_repo.get_by_id(item_id)
                if resource:
                    await self.resource_repo.update(
                        item_id,
                        access_count=(resource.access_count or 0) + 1,
                    )
            else:
                category = await self.category_repo.get_by_id(item_id)
                if category:
                    await self.category_repo.update(
                        item_id,
                        access_count=(category.access_count or 0) + 1,
                    )
            return True

        except Exception as e:
            logger.error(f"增加访问计数失败: {e}")
            return False

    # ========== 统计信息 ==========

    async def get_memory_stats(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """获取记忆库统计信息

        Returns:
            统计信息字典
        """
        # 获取分类统计
        category_stats = await self.category_repo.get_category_stats(user_id)

        # 获取 Resource 数量
        resources = await self.resource_repo.get_by_user_id(user_id, limit=1000)
        total_resources = len(resources)
        total_resource_importance = sum(r.importance_score for r in resources)
        total_resource_access = sum(r.access_count or 0 for r in resources)

        # 获取 Category（原子化信息）数量
        categories = await self.category_repo.get_by_user_id(user_id, limit=1000)
        total_categories = len(categories)
        total_category_importance = sum(c.importance_score for c in categories)
        total_category_access = sum(c.access_count or 0 for c in categories)

        avg_resource_importance = (
            total_resource_importance / total_resources if total_resources > 0 else 0
        )
        avg_category_importance = (
            total_category_importance / total_categories if total_categories > 0 else 0
        )

        return {
            "resources": {
                "total": total_resources,
                "avg_importance": round(avg_resource_importance, 2),
                "total_access": total_resource_access,
            },
            "atomic_items": {
                "total": total_categories,
                "avg_importance": round(avg_category_importance, 2),
                "total_access": total_category_access,
                "by_category": category_stats,
            },
        }
