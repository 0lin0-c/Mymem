from __future__ import annotations

from typing import Any


QA_CATEGORY_MEANINGS = {
    1: "事实回忆（单一事实）",
    2: "时间相关（when/how long）",
    3: "推理归纳（需要综合多事实）",
    4: "偏好态度",
    5: "无法回答（测试拒绝能力）",
}


def category_label(category: Any) -> str:
    try:
        category_id = int(category)
    except (TypeError, ValueError):
        return "未知类别"
    return QA_CATEGORY_MEANINGS.get(category_id, "未知类别")


def format_qa_category(category: Any) -> str:
    try:
        category_id = int(category)
    except (TypeError, ValueError):
        return f"Category {category} - 未知类别"
    return f"Category {category_id} - {category_label(category_id)}"
