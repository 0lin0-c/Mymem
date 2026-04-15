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


def build_memory_extraction_prompt(categories: List[Dict]) -> str:
    """构建记忆提取 prompt

    Args:
        categories: 分类列表，每个元素包含 name, description

    Returns:
        格式化后的 prompt 字符串
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not categories:
        category_details = "暂无分类信息。"
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
        "description": "从对话中提取综合摘要和原子化记忆信息",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "对话的综合摘要，以第三人称客观陈述",
                },
                "importance_score": {
                    "type": "integer",
                    "description": "对综合摘要的整体重要性评分 1-10",
                    "minimum": 1,
                    "maximum": 10,
                },
                "response_summary": {
                    "type": "string",
                    "description": "AI 回复的核心要点摘要，若无回复则为空字符串",
                },
                "atomic_items": {
                    "type": "array",
                    "description": "从对话中提取的原子化信息列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category_name": {
                                "type": "string",
                                "description": "分类名称",
                            },
                            "content": {
                                "type": "string",
                                "description": "原子化的记忆内容",
                            },
                            "importance_score": {
                                "type": "integer",
                                "description": "该条信息的重要性评分 1-10",
                                "minimum": 1,
                                "maximum": 10,
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

# Anthropic Tool Use 格式
EXTRACT_MEMORY_TOOL_ANTHROPIC = {
    "name": "extract_memory",
    "description": "从对话中提取综合摘要和原子化记忆信息",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "对话的综合摘要，以第三人称客观陈述",
            },
            "importance_score": {
                "type": "integer",
                "description": "对综合摘要的整体重要性评分 1-10",
            },
            "response_summary": {
                "type": "string",
                "description": "AI 回复的核心要点摘要，若无回复则为空字符串",
            },
            "atomic_items": {
                "type": "array",
                "description": "从对话中提取的原子化信息列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_name": {
                            "type": "string",
                            "description": "分类名称",
                        },
                        "content": {
                            "type": "string",
                            "description": "原子化的记忆内容",
                        },
                        "importance_score": {
                            "type": "integer",
                            "description": "该条信息的重要性评分 1-10",
                        },
                    },
                    "required": ["category_name", "content", "importance_score"],
                },
            },
        },
        "required": ["summary", "importance_score", "response_summary", "atomic_items"],
    },
}
