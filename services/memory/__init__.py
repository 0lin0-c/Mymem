# 📦 记忆服务模块
from services.memory.writer import MemoryWriter
from services.memory.lifecycle import MemoryLifecycle
from services.memory.deduplicator import MemoryDeduplicator, DedupAction, DedupResult
from services.memory.dedup_config import (
    DedupThreshold,
    CATEGORY_DEDUP_THRESHOLDS,
    RESOURCE_DEDUP_THRESHOLD,
    DEFAULT_DEDUP_THRESHOLD,
    get_threshold_for_category,
    cosine_distance_to_similarity,
    similarity_to_cosine_distance,
)

__all__ = [
    "MemoryWriter",
    "MemoryLifecycle",
    "MemoryDeduplicator",
    "DedupAction",
    "DedupResult",
    "DedupThreshold",
    "CATEGORY_DEDUP_THRESHOLDS",
    "RESOURCE_DEDUP_THRESHOLD",
    "DEFAULT_DEDUP_THRESHOLD",
    "get_threshold_for_category",
    "cosine_distance_to_similarity",
    "similarity_to_cosine_distance",
]
