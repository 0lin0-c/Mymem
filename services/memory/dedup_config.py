# ⚖️ 记忆去重配置：定义各分类的相似度阈值
from dataclasses import dataclass
from typing import Dict


@dataclass
class DedupThreshold:
    """去重阈值配置"""
    skip_threshold: float  # 相似度 >= 此值则跳过（强化已有）
    merge_threshold: float  # 相似度在此范围内则合并


# 各分类的去重阈值
CATEGORY_DEDUP_THRESHOLDS: Dict[str, DedupThreshold] = {
    "核心自我": DedupThreshold(
        skip_threshold=0.85,  # 核心自我信息高度相似则跳过
        merge_threshold=0.75,  # 75%-85% 合并
    ),
    "情景时间轴": DedupThreshold(
        skip_threshold=0.90,  # 情景信息需要更高相似度才跳过
        merge_threshold=0.75,  # 75%-90% 合并
    ),
    "语义知识库": DedupThreshold(
        skip_threshold=0.88,  # 知识信息较高相似度跳过
        merge_threshold=0.75,  # 75%-88% 合并
    ),
    "社交关系图谱": DedupThreshold(
        skip_threshold=0.85,  # 社交信息较高相似度跳过
        merge_threshold=0.75,  # 75%-85% 合并
    ),
    "动态领域分类": DedupThreshold(
        skip_threshold=0.92,  # 动态分类需要非常高相似度才跳过
        merge_threshold=0.75,  # 75%-92% 合并
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
