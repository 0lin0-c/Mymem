# 🔧 LLM 工具定义：Function Calling / Tool Use 的公共定义
import math
from datetime import datetime
from typing import Dict, List

from services.prompts import CHAT_SYSTEM_PROMPT, CHAT_USER_PROMPT, MEMORY_EXTRACTION_PROMPT, MEMORY_MERGE_PROMPT


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


def build_memory_extraction_prompt(categories: List[Dict], reference_time: str | None = None) -> str:
    """构建记忆提取 prompt

    Args:
        categories: 分类列表，每个元素包含 name, description
        reference_time: 参考时间戳（可选，用于历史数据导入）。不传则使用系统当前时间。

    Returns:
        格式化后的 prompt 字符串
    """
    current_time = reference_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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


def build_memory_merge_prompt(existing_memory: str, new_input: str) -> str:
    """构建记忆合并判断 prompt"""
    return MEMORY_MERGE_PROMPT.format(
        existing_memory=existing_memory,
        new_input=new_input,
    )


# ========== Tool 定义 ==========

# OpenAI Function Calling 格式
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
                        "properties": {
                            "category_name": {
                                "type": "string",
                                "description": "The category name, copied exactly from the provided taxonomy.",
                            },
                            "content": {
                                "type": "string",
                                "description": "The atomic memory content.",
                            },
                            "importance_score": {
                                "type": "integer",
                                "description": "Importance score for this atomic item, from 0 to 3.",
                                "minimum": 0,
                                "maximum": 3,
                            },
                        },
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
                    "properties": {
                        "category_name": {
                            "type": "string",
                            "description": "The category name, copied exactly from the provided taxonomy.",
                        },
                        "content": {
                            "type": "string",
                            "description": "The atomic memory content.",
                        },
                        "importance_score": {
                            "type": "integer",
                            "description": "Importance score for this atomic item, from 0 to 3.",
                        },
                    },
                    "required": ["category_name", "content", "importance_score"],
                },
            },
        },
        "required": ["summary", "importance_score", "response_summary", "atomic_items"],
    },
}
