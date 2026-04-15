# ✍️ 记忆写入服务：Handler 模式分发器
import logging
from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from tables import User
from repositories import (
    UserRepository,
    CategoryRepository,
    ResourceRepository,
    ResourceCategoryRepository,
)
from services.llm.base import BaseLLMProvider
from services.oss.base import BaseOSSClient
from services.oss.local_client import LocalOSSClient
from services.memory.handlers import get_handler
from services.memory.deduplicator import MemoryDeduplicator, DedupAction
from services.constants import BASE_CATEGORIES

logger = logging.getLogger(__name__)


def _format_categories_for_prompt(categories: List[dict]) -> List[dict]:
    """将分类列表格式化为 prompt 所需的格式"""
    return [
        {
            "name": c.get("name", ""),
            "description": c.get("description", ""),
        }
        for c in categories
    ]


class MemoryWriter:
    """记忆写入服务

    职责：
    1. 根据 modality 分发到对应的 Handler
    2. LLM 提取综合摘要和原子化信息
    3. 创建 Resource（存综合摘要）- 带去重
    4. 批量创建 Category（存原子化信息）- 带去重
    5. 创建 ResourceCategory 关联（追踪来源）
    """

    def __init__(
        self,
        session: AsyncSession,
        llm: BaseLLMProvider,
        oss_client: BaseOSSClient | None = None,
        enable_dedup: bool = True,
    ):
        self.session = session
        self.llm = llm
        self.oss_client = oss_client or LocalOSSClient()
        self.enable_dedup = enable_dedup

        self.user_repo = UserRepository(session)
        self.category_repo = CategoryRepository(session)
        self.resource_repo = ResourceRepository(session)
        self.rc_repo = ResourceCategoryRepository(session)

        # 初始化去重服务
        self.deduplicator = MemoryDeduplicator(session, llm) if enable_dedup else None

    async def save_chat(
        self,
        user_id: str,
        user_input: Any,
        assistant_response: str,
        modality: str = "text",
        user_categories: List[dict] | None = None,
    ) -> dict:
        """保存用户与 AI 的对话到记忆

        流程：
        1. 预处理用户输入
        2. LLM 提取综合摘要和原子化信息
        3. [去重] Resource 级别去重检查
        4. 创建/更新 Resource（存综合摘要）
        5. [去重] Category 级别去重检查（每个 atomic_item）
        6. 批量创建/更新 Category（存原子化信息）
        7. 创建 ResourceCategory 关联

        Args:
            user_id: 用户 ID
            user_input: 用户输入（文本/文件字节等）
            assistant_response: AI 回复
            modality: 模态类型
            user_categories: 用户的 6 个分类列表（可选，用于 prompt）

        Returns:
            dict: 包含 resource_id, atomic_items 等信息
        """
        # 验证用户存在
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"用户不存在: {user_id}")

        # ========== Step 1: 获取 Handler 并预处理 ==========
        handler_class = get_handler(modality)
        handler = handler_class(
            session=self.session,
            llm=self.llm,
            oss_client=self.oss_client,
            user_id=user_id,
        )

        preprocessed_text = await handler.preprocess(user_input)
        raw_content_stored = await handler.store_raw_content(user_input)

        # ========== Step 2: 准备分类列表 ==========
        if user_categories is None:
            user_categories = BASE_CATEGORIES
        categories_for_prompt = _format_categories_for_prompt(user_categories)

        # ========== Step 3: LLM 提取综合摘要和原子化信息 ==========
        memory_intent = await self.llm.extract_memory_intent(
            text=preprocessed_text,
            categories=categories_for_prompt,
            assistant_response=assistant_response,
        )

        summary = memory_intent.get("summary", preprocessed_text)
        importance_score = memory_intent.get("importance_score", 5)
        response_summary = memory_intent.get("response_summary", "")
        atomic_items = memory_intent.get("atomic_items", [])

        # ========== Step 4: 生成综合摘要的向量 ==========
        embedding_vector = await self._get_embedding(summary)

        # ========== Step 5: Resource 级别去重检查 ==========
        resource = None
        dedup_info = {"action": "create", "similarity": 0.0}

        if self.deduplicator:
            dedup_result = await self.deduplicator.check_resource_duplicate(
                user_id=user_id,
                summary=summary,
                vector=embedding_vector,
            )
            dedup_info["action"] = dedup_result.action.value
            dedup_info["similarity"] = dedup_result.similarity

            if dedup_result.action == DedupAction.SKIP:
                # 强化已有 Resource，不创建新的
                await self.deduplicator.reinforce_resource(dedup_result.existing_item)
                logger.info(
                    f"Resource 去重跳过: similarity={dedup_result.similarity:.3f}, "
                    f"reason={dedup_result.reason}"
                )
                resource = dedup_result.existing_item

            elif dedup_result.action in (DedupAction.MERGE, DedupAction.UPDATE):
                # 合并/更新已有 Resource
                if dedup_result.merged_content:
                    merged_vector = await self._get_embedding(dedup_result.merged_content)
                    resource = await self.deduplicator.merge_resource(
                        existing=dedup_result.existing_item,
                        merged_content=dedup_result.merged_content,
                        merged_vector=merged_vector,
                    )
                    logger.info(
                        f"Resource {dedup_result.action.value}: similarity={dedup_result.similarity:.3f}"
                    )
                else:
                    resource = dedup_result.existing_item

        # ========== Step 6: 创建 Resource（如果需要）==========
        if resource is None:
            resource = await self.resource_repo.create(
                user_id=user_id,
                raw_content=raw_content_stored,
                modality=modality,
                description=summary,
                description_vector=embedding_vector,
                importance_score=importance_score,
                assistant_response=response_summary,
            )

        # ========== Step 7: 批量创建 Category（带去重）==========
        created_items = []
        category_ids = []

        if atomic_items:
            for item in atomic_items:
                category_name = item.get("category_name", "语义知识库")
                content = item.get("content", "")
                item_importance = item.get("importance_score", 5)

                # Category 级别去重检查
                category = None

                if self.deduplicator:
                    item_vector = await self._get_embedding(content)
                    cat_dedup = await self.deduplicator.check_category_duplicate(
                        user_id=user_id,
                        category_name=category_name,
                        content=content,
                        vector=item_vector,
                    )

                    if cat_dedup.action == DedupAction.SKIP:
                        # 强化已有 Category
                        await self.deduplicator.reinforce_category(cat_dedup.existing_item)
                        logger.info(
                            f"Category 去重跳过: category={category_name}, "
                            f"similarity={cat_dedup.similarity:.3f}"
                        )
                        category = cat_dedup.existing_item

                    elif cat_dedup.action in (DedupAction.MERGE, DedupAction.UPDATE):
                        # 合并/更新已有 Category
                        if cat_dedup.merged_content:
                            # 为合并后的内容生成向量
                            merged_vector = await self._get_embedding(cat_dedup.merged_content)
                            category = await self.deduplicator.merge_category(
                                existing=cat_dedup.existing_item,
                                merged_content=cat_dedup.merged_content,
                                merged_vector=merged_vector,
                                importance_score=item_importance,
                            )
                            logger.info(
                                f"Category {cat_dedup.action.value}: category={category_name}"
                            )
                        else:
                            category = cat_dedup.existing_item

                # 创建新的 Category
                if category is None:
                    # 使用已生成的向量，避免重复调用 LLM
                    category = await self.category_repo.create_item(
                        user_id=user_id,
                        category_name=category_name,
                        content=content,
                        content_vector=item_vector,
                        importance_score=item_importance,
                    )

                created_items.append(category)
                category_ids.append(category.id)

        # ========== Step 8: 创建 ResourceCategory 关联 ==========
        if category_ids:
            await self.rc_repo.create_relations_batch(
                resource_id=resource.id,
                category_ids=category_ids,
                relation_type="created",
            )

        logger.info(
            f"记忆保存完成: resource_id={resource.id}, "
            f"atomic_items={len(created_items)}, dedup={dedup_info['action']}"
        )

        return {
            "resource_id": resource.id,
            "summary": summary,
            "importance_score": importance_score,
            "atomic_items_count": len(created_items),
            "dedup_info": dedup_info,
            "atomic_items": [
                {
                    "id": item.id,
                    "category_name": item.category_name,
                    "content": item.content,
                    "importance_score": item.importance_score,
                }
                for item in created_items
            ],
        }

    async def _get_embedding(self, text: str) -> list[float]:
        """获取文本的向量表示

        Returns:
            向量（维度由 embedding_dimensions 配置）
        """
        return await self.llm.get_embedding(text)
