# Deduplication Configuration: Define similarity thresholds for each category
from dataclasses import dataclass
from typing import Dict


@dataclass
class DedupThreshold:
    """Dedup threshold configuration"""
    skip_threshold: float  # similarity >= this value then skip (reinforce existing)
    merge_threshold: float  # similarity in this range then merge


# Dedup thresholds for each category
CATEGORY_DEDUP_THRESHOLDS: Dict[str, DedupThreshold] = {
    "Core Self": DedupThreshold(
        skip_threshold=0.85,  # Core Self info skips if highly similar
        merge_threshold=0.75,  # 75%-85% merge
    ),
    "Timeline": DedupThreshold(
        skip_threshold=0.90,  # Timeline info needs higher similarity to skip
        merge_threshold=0.75,  # 75%-90% merge
    ),
    "Knowledge Base": DedupThreshold(
        skip_threshold=0.88,  # Knowledge info skips at higher similarity
        merge_threshold=0.75,  # 75%-88% merge
    ),
    "Social Graph": DedupThreshold(
        skip_threshold=0.85,  # Social info skips at higher similarity
        merge_threshold=0.75,  # 75%-85% merge
    ),
    "Dynamic Category": DedupThreshold(
        skip_threshold=0.92,  # Dynamic categories need very high similarity to skip
        merge_threshold=0.75,  # 75%-92% merge
    ),
}

# Resource 级别的默认阈值（用于综合摘要去重）
RESOURCE_DEDUP_THRESHOLD = DedupThreshold(
    skip_threshold=0.90,  # Resource 级别需要高相似度才跳过
    merge_threshold=0.80,  # 80%-90% 合并
)

# 默认阈值（用于未定义的分类）
DEFAULT_DEDUP_THRESHOLD = DedupThreshold(
    skip_threshold=0.88,
    merge_threshold=0.75,
)


def get_threshold_for_category(category_name: str) -> DedupThreshold:
    """获取指定分类的去重阈值

    Args:
        category_name: 分类名称

    Returns:
        DedupThreshold 实例
    """
    return CATEGORY_DEDUP_THRESHOLDS.get(category_name, DEFAULT_DEDUP_THRESHOLD)


def cosine_distance_to_similarity(cosine_distance: float) -> float:
    """将余弦距离转换为相似度

    pgvector 的 <=> 算子返回余弦距离，范围 0~1（归一化向量）。
    相似度 = 1 - cosine_distance

    Args:
        cosine_distance: 余弦距离

    Returns:
        相似度 (0-1)
    """
    return 1 - cosine_distance


def similarity_to_cosine_distance(similarity: float) -> float:
    """将相似度转换为余弦距离

    Args:
        similarity: 相似度 (0-1)

    Returns:
        余弦距离
    """
    return 1 - similarity
