# 🔧 LLM 工具定义：Function Calling / Tool Use 的公共定义
import math
from datetime import datetime
from typing import Dict, List

from services.constants import (
    EPISODIC_MEMORY_CATEGORY,
    normalize_category_name,
)
from services.prompts import (
    CATEGORY_MEMORY_EXTRACTION_PROMPT,
    CHAT_SYSTEM_PROMPT,
    CHAT_USER_PROMPT,
    CORE_SELF_EXTRACTION_REQUIREMENTS,
    EPISODIC_MEMORY_EXTRACTION_REQUIREMENTS,
    GENERIC_CATEGORY_EXTRACTION_REQUIREMENTS,
    KNOWLEDGE_BASE_EXTRACTION_REQUIREMENTS,
    MEMORY_EXTRACTION_PROMPT,
    MEMORY_MERGE_PROMPT,
    SOCIAL_GRAPH_EXTRACTION_REQUIREMENTS,
)


# ========== 向量计算函数 ==========

def cosine_similarity_from_bytes(vec1_bytes: bytes, vec2_bytes: bytes) -> float:
    """计算两个向量的余弦相似度"""
    import struct

    vec1 = struct.unpack(f'{len(vec1_bytes) // 4}f', vec1_bytes)
    vec2 = struct.unpack(f'{len(vec2_bytes) // 4}f', vec2_bytes)

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def cosine_distance_to_similarity(distance: float) -> float:
    """将余弦距离转换为相似度

    pgvector 的 <=> 算子返回余弦距离。
    similarity = 1 - distance（与 scoring.md 规范一致）
    """
    return 1 - distance


# ========== Prompt 构建函数 ==========

def build_chat_prompt(context: str, user_query: str) -> Dict[str, str]:
    """构建对话 prompt"""
    return {
        "system_prompt": CHAT_SYSTEM_PROMPT,
        "user_prompt": CHAT_USER_PROMPT.format(
            context=context,
            user_query=user_query,
        ),
    }


FIXED_CATEGORY_EXTRACTION_REQUIREMENTS = {
    "Core Self": CORE_SELF_EXTRACTION_REQUIREMENTS,
    EPISODIC_MEMORY_CATEGORY: EPISODIC_MEMORY_EXTRACTION_REQUIREMENTS,
    "Knowledge Base": KNOWLEDGE_BASE_EXTRACTION_REQUIREMENTS,
    "Social Graph": SOCIAL_GRAPH_EXTRACTION_REQUIREMENTS,
}


def build_memory_extraction_prompt(
    categories: List[Dict],
    reference_time: str | None = None,
    target_category_name: str | None = None,
) -> str:
    """构建记忆提取 prompt

    Args:
        categories: 分类列表，每个元素包含 name, description
        reference_time: 参考时间戳（可选，用于历史数据导入）。不传则使用系统当前时间。

    Returns:
        格式化后的 prompt 字符串
    """
    current_time = reference_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if target_category_name:
        return build_category_memory_extraction_prompt(
            categories=categories,
            target_category_name=target_category_name,
            reference_time=reference_time,
        )

    if not categories:
        category_details = "No category information is available."
    else:
        lines = []
        for i, cat in enumerate(categories, 1):
            name = cat.get("name", "")
            description = cat.get("description", "")
            lines.append(f"{i}. [{name}]: {description}")
        category_details = "\n".join(lines)

    return MEMORY_EXTRACTION_PROMPT.format(
        current_time=current_time,
        category_details=category_details,
    )


def build_category_memory_extraction_prompt(
    categories: List[Dict],
    target_category_name: str,
    reference_time: str | None = None,
) -> str:
    """Build a MemU-style extraction prompt for one target category."""
    current_time = reference_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_target = normalize_category_name(target_category_name)
    description = ""
    for category in categories:
        name = normalize_category_name(str(category.get("name", "")))
        if name == normalized_target:
            description = str(category.get("description", ""))
            break
    requirements = FIXED_CATEGORY_EXTRACTION_REQUIREMENTS.get(
        normalized_target,
        GENERIC_CATEGORY_EXTRACTION_REQUIREMENTS,
    )
    return CATEGORY_MEMORY_EXTRACTION_PROMPT.format(
        current_time=current_time,
        category_name=normalized_target,
        category_description=description or f"User-specific memories related to {normalized_target}",
        category_requirements=requirements,
    )


def build_memory_merge_prompt(existing_memory: str, new_input: str) -> str:
    """构建记忆合并判断 prompt"""
    return MEMORY_MERGE_PROMPT.format(
        existing_memory=existing_memory,
        new_input=new_input,
    )


# ========== Tool 定义 ==========

# OpenAI Function Calling 格式
ATOMIC_ITEM_METADATA_PROPERTIES = {
    "memory_type": {
        "type": "string",
        "description": "Type-aware memory label for the atomic item.",
        "enum": [
            "profile_fact",
            "event_fact",
            "exact_fact",
            "symbolic_meaning",
            "advice_checklist",
            "relationship_fact",
            "media_fact",
            "knowledge_fact",
        ],
    },
    "fact_type": {
        "type": "string",
        "description": "Optional specific fact label such as who_did_what, time, location, yes_no, negation, ownership, event_topic, object_relation, symbol_meaning, checklist, or preference.",
    },
    "subject": {
        "type": "string",
        "description": "Who or what this memory is about, usually the user or a named person/object.",
    },
    "source_role": {
        "type": "string",
        "description": "The source speaker for the stored fact. Current storage should use user-confirmed facts.",
        "enum": ["user"],
    },
    "time_text": {
        "type": "string",
        "description": "Original time expression from the user input, or an empty string if none was stated.",
    },
    "confidence": {
        "type": "number",
        "description": "Confidence that the fact is directly supported by the user input, from 0.0 to 1.0.",
        "minimum": 0.0,
        "maximum": 1.0,
    },
    "extraction_origin": {
        "type": "string",
        "description": "Evidence origin used only for write-time quality filtering.",
        "enum": [
            "direct_user_statement",
            "quoted_first_person",
            "third_person_narrative",
            "assistant_advice",
            "surviving_need",
            "forget_instruction",
        ],
    },
}


def _atomic_item_properties() -> Dict:
    return {
        "category_name": {
            "type": "string",
            "description": "The category name, copied exactly from the provided taxonomy.",
        },
        "content": {
            "type": "string",
            "description": "The normalized atomic memory fact. Do not include raw quotes.",
        },
        "importance_score": {
            "type": "integer",
            "description": "Importance score for this atomic item, from 0 to 3.",
            "minimum": 0,
            "maximum": 3,
        },
        **ATOMIC_ITEM_METADATA_PROPERTIES,
    }


EXTRACT_MEMORY_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "extract_memory",
        "description": "Extract a comprehensive summary and atomic memory items from the conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "A comprehensive objective third-person summary of the conversation.",
                },
                "importance_score": {
                    "type": "integer",
                    "description": "Overall importance score for the summary, from 0 to 3.",
                    "minimum": 0,
                    "maximum": 3,
                },
                "response_summary": {
                    "type": "string",
                    "description": "A concise summary of the AI response; use an empty string if there is no response.",
                },
                "atomic_items": {
                    "type": "array",
                    "description": "A list of independent atomic memory items extracted from the conversation.",
                    "items": {
                        "type": "object",
                        "properties": _atomic_item_properties(),
                        "required": ["category_name", "content", "importance_score"],
                    },
                },
            },
            "required": ["summary", "importance_score", "response_summary", "atomic_items"],
        },
    },
}

# Anthropic Tool Use format
EXTRACT_MEMORY_TOOL_ANTHROPIC = {
    "name": "extract_memory",
    "description": "Extract a comprehensive summary and atomic memory items from the conversation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A comprehensive objective third-person summary of the conversation.",
            },
            "importance_score": {
                "type": "integer",
                "description": "Overall importance score for the summary, from 0 to 3.",
            },
            "response_summary": {
                "type": "string",
                "description": "A concise summary of the AI response; use an empty string if there is no response.",
            },
            "atomic_items": {
                "type": "array",
                "description": "A list of independent atomic memory items extracted from the conversation.",
                "items": {
                    "type": "object",
                    "properties": _atomic_item_properties(),
                    "required": ["category_name", "content", "importance_score"],
                },
            },
        },
        "required": ["summary", "importance_score", "response_summary", "atomic_items"],
    },
}
