# ⚙️ LLM 设置契约：定义用户 LLM 配置的请求/响应格式
from pydantic import BaseModel, Field


class LLMSettingsRequest(BaseModel):
    """用户 LLM 配置请求"""
    user_id: str = Field(..., description="用户ID")
    llm_provider: str = Field(..., description="LLM 提供商: openai/deepseek/qwen/glm/anthropic/custom")
    llm_api_key: str = Field(..., description="LLM API Key")
    llm_base_url: str | None = Field(None, description="LLM API Base URL（可选）")
    llm_model: str = Field(..., description="LLM 模型名称")


class LLMSettingsResponse(BaseModel):
    """用户 LLM 配置响应"""
    success: bool
    message: str = ""
    warmed_up: bool = False
