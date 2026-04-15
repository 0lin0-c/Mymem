# 📝 Prompts 包：集中管理所有 Prompt 模板
from services.prompts.chat_prompt import CHAT_SYSTEM_PROMPT, CHAT_USER_PROMPT
from services.prompts.memory_prompt import MEMORY_EXTRACTION_PROMPT
from services.prompts.onboarding_prompt import DYNAMIC_CATEGORY_PROMPT
from services.prompts.lifecycle_prompt import MEMORY_MERGE_PROMPT

__all__ = [
    "CHAT_SYSTEM_PROMPT",
    "CHAT_USER_PROMPT",
    "MEMORY_EXTRACTION_PROMPT",
    "DYNAMIC_CATEGORY_PROMPT",
    "MEMORY_MERGE_PROMPT",
]
