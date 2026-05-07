# ✍️ 记忆写入服务：Handler 模式分发器
import logging
import re
from typing import Any, List
from datetime import datetime

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
from services.constants import (
    BASE_CATEGORIES,
    EPISODIC_MEMORY_CATEGORY,
    LEGACY_TIMELINE_CATEGORY,
    normalize_category_name,
)

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_ATOMIC_METADATA_KEYS = (
    "memory_type",
    "fact_type",
    "subject",
    "source_role",
    "time_text",
    "confidence",
    "extraction_origin",
)

_CORE_SELF_CATEGORY = "Core Self"
_KNOWLEDGE_BASE_CATEGORY = "Knowledge Base"
_MIN_STORAGE_CONFIDENCE = 0.45
_BOOSTED_ORIGINS = {"direct_user_statement", "forget_instruction", "surviving_need"}
_ADVICE_ALLOWED_CATEGORIES = {EPISODIC_MEMORY_CATEGORY, _KNOWLEDGE_BASE_CATEGORY}


def _format_categories_for_prompt(categories: List[dict]) -> List[dict]:
    """将分类列表格式化为 prompt 所需的格式"""
    return [
        {
            "name": c.get("name", ""),
            "description": c.get("description", ""),
        }
        for c in categories
    ]


def _extract_atomic_metadata(item: dict[str, Any]) -> dict[str, Any]:
    """Keep non-persistent extraction metadata for trace/evaluation output."""
    metadata = {
        key: item.get(key)
        for key in _ATOMIC_METADATA_KEYS
        if item.get(key) not in (None, "")
    }
    if "source_role" not in metadata:
        metadata["source_role"] = "user"
    return metadata


def _coerce_confidence(item: dict[str, Any]) -> float:
    """Return a bounded confidence value while keeping old prompts compatible."""
    raw_confidence = item.get("confidence", 1.0)
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 1.0
    return min(max(confidence, 0.0), 1.0)


def _coerce_importance(item: dict[str, Any]) -> int:
    """Return the supported 0-3 importance score."""
    try:
        importance = int(item.get("importance_score", 2))
    except (TypeError, ValueError):
        importance = 2
    return min(max(importance, 0), 3)


def _normalize_atomic_item_for_storage(item: dict[str, Any]) -> dict[str, Any] | None:
    """Apply no-migration evidence quality rules before Category persistence.

    The extraction metadata is intentionally not persisted as table columns. It is
    converted here into either a filtered item or an adjusted importance score.
    """
    if not isinstance(item, dict):
        return None

    content = str(item.get("content", "")).strip()
    if not content:
        return None

    normalized = dict(item)
    normalized["content"] = content
    normalized["category_name"] = normalize_category_name(
        str(item.get("category_name", "Knowledge Base")).strip()
    )

    confidence = _coerce_confidence(item)
    normalized["confidence"] = confidence
    if confidence < _MIN_STORAGE_CONFIDENCE:
        return None

    origin = str(item.get("extraction_origin", "")).strip()
    memory_type = str(item.get("memory_type", "")).strip()
    category_name = normalized["category_name"]
    importance = _coerce_importance(item)

    if origin == "third_person_narrative":
        if category_name == _CORE_SELF_CATEGORY:
            return None
        importance = min(importance, 1)

    if origin == "quoted_first_person":
        importance = min(importance, 2)

    if origin in _BOOSTED_ORIGINS:
        importance = max(importance, 2)
    if origin == "forget_instruction":
        importance = max(importance, 3)

    if origin == "assistant_advice":
        if memory_type != "advice_checklist" or category_name not in _ADVICE_ALLOWED_CATEGORIES:
            return None

    normalized["importance_score"] = min(max(importance, 0), 3)
    return normalized


def _detect_source_language(text: str) -> str:
    """Detect the dominant language for storage guardrails."""
    if not text:
        return "unknown"

    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))

    if cjk_count == 0 and latin_count >= 3:
        return "en"
    if cjk_count >= 2 and cjk_count > latin_count:
        return "zh"
    if cjk_count > 0 and latin_count > 0:
        return "mixed"
    return "unknown"


def _violates_source_language(text: str, source_language: str) -> bool:
    """Return True when model output should not be stored for the source language."""
    if not text:
        return False
    if source_language == "en":
        return bool(_CJK_RE.search(text))
    return False


def _apply_language_guard(
    memory_intent: dict,
    source_text: str,
) -> tuple[dict, dict]:
    """Prevent model language drift from entering storage."""
    source_language = _detect_source_language(source_text)
    if source_language != "en":
        return memory_intent, {
            "source_language": source_language,
            "summary_replaced": False,
            "response_summary_cleared": False,
            "dropped_atomic_items": 0,
        }

    guarded = dict(memory_intent)
    summary = guarded.get("summary") or source_text
    response_summary = guarded.get("response_summary") or ""
    atomic_items = guarded.get("atomic_items") or []

    summary_replaced = False
    response_summary_cleared = False

    if _violates_source_language(summary, source_language):
        guarded["summary"] = source_text[:500]
        summary_replaced = True

    if _violates_source_language(response_summary, source_language):
        guarded["response_summary"] = ""
        response_summary_cleared = True

    filtered_items = []
    dropped_count = 0
    for item in atomic_items:
        content = item.get("content", "") if isinstance(item, dict) else ""
        if _violates_source_language(content, source_language):
            dropped_count += 1
            continue
        filtered_items.append(item)
    guarded["atomic_items"] = filtered_items

    return guarded, {
        "source_language": source_language,
        "summary_replaced": summary_replaced,
        "response_summary_cleared": response_summary_cleared,
        "dropped_atomic_items": dropped_count,
    }


def _target_category_names(categories: List[dict]) -> List[str]:
    """Return normalized category names while preserving prompt order."""
    names: List[str] = []
    for category in categories:
        name = normalize_category_name(str(category.get("name", "")).strip())
        if name and name not in names:
            names.append(name)
    return names


def _filter_atomic_items_for_category(
    memory_intent: dict,
    target_category_name: str,
) -> list[dict[str, Any]]:
    """Keep only atomic items that belong to the current target category."""
    target = normalize_category_name(target_category_name)
    filtered: list[dict[str, Any]] = []
    for item in memory_intent.get("atomic_items") or []:
        if not isinstance(item, dict):
            continue
        category_name = normalize_category_name(str(item.get("category_name", "")).strip())
        if category_name != target:
            continue
        normalized_item = _normalize_atomic_item_for_storage(item)
        if not normalized_item:
            continue
        normalized_item["category_name"] = target
        filtered.append(normalized_item)
    return filtered


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
        reference_time: str | None = None,
        memory_time: datetime | None = None,
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
            reference_time: 参考时间戳（可选，用于历史数据导入，格式 "YYYY-MM-DD HH:MM:SS"）
            memory_time: 记忆发生时间（可选，用于历史数据导入时写入 created_at/updated_at）

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
            # 默认包含固定分类，再补充用户已有的动态分类
            user_categories = [
                {"name": c["name"], "description": c["description"]}
                for c in BASE_CATEGORIES
            ]

            category_stats = await self.category_repo.get_category_stats(user_id)
            if category_stats:
                base_category_names = {c["name"] for c in user_categories} | {LEGACY_TIMELINE_CATEGORY}
                for category_name in category_stats.keys():
                    normalized_name = normalize_category_name(category_name)
                    if normalized_name not in base_category_names:
                        user_categories.append({
                            "name": normalized_name,
                            "description": f"User-specific memories related to {normalized_name}",
                        })
        categories_for_prompt = _format_categories_for_prompt(user_categories)

        # ========== Step 3: LLM 提取综合摘要和原子化信息 ==========
        memory_intent = await self.llm.extract_memory_intent(
            text=preprocessed_text,
            categories=categories_for_prompt,
            assistant_response=assistant_response,
            reference_time=reference_time,
        )
        memory_intent, language_guard_info = _apply_language_guard(
            memory_intent,
            preprocessed_text,
        )
        if (
            language_guard_info["summary_replaced"]
            or language_guard_info["response_summary_cleared"]
            or language_guard_info["dropped_atomic_items"] > 0
        ):
            logger.info(
                "Language guard applied: source=%s, summary_replaced=%s, "
                "response_summary_cleared=%s, dropped_atomic_items=%s",
                language_guard_info["source_language"],
                language_guard_info["summary_replaced"],
                language_guard_info["response_summary_cleared"],
                language_guard_info["dropped_atomic_items"],
            )

        summary = memory_intent.get("summary", preprocessed_text)
        importance_score = memory_intent.get("importance_score", 2)
        response_summary = memory_intent.get("response_summary", "")
        # The first extraction pass is intentionally a summary pass only. Atomic
        # memories are written from per-category extraction so category boundaries
        # stay explicit and do not depend on one broad multi-category prompt.
        atomic_items = await self._extract_atomic_items_by_category(
            text=preprocessed_text,
            assistant_response=assistant_response,
            categories=categories_for_prompt,
            reference_time=reference_time,
        )

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
                created_at=memory_time,
                updated_at=memory_time,
            )
        elif memory_time is not None:
            resource.updated_at = memory_time

        # ========== Step 7: 批量创建 Category（带去重）==========
        created_items = []
        created_item_outputs = []
        category_ids = []

        if atomic_items:
            for item in atomic_items:
                category_name = normalize_category_name(item.get("category_name", "Knowledge Base"))
                content = item.get("content", "")
                item_importance = item.get("importance_score", 2)
                item_vector = await self._get_embedding(content)

                # Category 级别去重检查
                category = None

                if self.deduplicator:
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
                        created_at=memory_time,
                        updated_at=memory_time,
                    )
                elif memory_time is not None:
                    category.updated_at = memory_time

                created_items.append(category)
                created_item_outputs.append({
                    "id": category.id,
                    "category_name": category.category_name,
                    "content": category.content,
                    "importance_score": category.importance_score,
                    "metadata": _extract_atomic_metadata(item),
                })
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
            "language_guard": language_guard_info,
            "atomic_items": created_item_outputs,
        }

    async def _extract_atomic_items_by_category(
        self,
        text: str,
        assistant_response: str,
        categories: List[dict],
        reference_time: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract atomic memories with one LLM call per target category."""
        all_items: list[dict[str, Any]] = []
        for target_category_name in _target_category_names(categories):
            category_intent = await self.llm.extract_memory_intent(
                text=text,
                categories=categories,
                assistant_response=assistant_response,
                reference_time=reference_time,
                target_category_name=target_category_name,
            )
            category_intent, category_language_guard = _apply_language_guard(
                category_intent,
                text,
            )
            if category_language_guard["dropped_atomic_items"] > 0:
                logger.info(
                    "Category extraction language guard applied: target=%s, dropped_atomic_items=%s",
                    target_category_name,
                    category_language_guard["dropped_atomic_items"],
                )
            all_items.extend(
                _filter_atomic_items_for_category(
                    category_intent,
                    target_category_name,
                )
            )

        return all_items

    async def _get_embedding(self, text: str) -> list[float]:
        """获取文本的向量表示

        Returns:
            向量（维度由 embedding_dimensions 配置）
        """
        return await self.llm.get_embedding(text)
