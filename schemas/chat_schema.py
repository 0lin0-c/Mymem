# 💬 对话契约：定义用户发消息的请求体以及返回给前端的响应体格式。
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str = Field(..., description="会话ID，用于区分不同对话窗口")
    query: str = Field(..., description="用户输入")
    user_id: Optional[str] = Field(default=None, description="用户ID，有前端登录时从 Token 解析传入")
    modality: str = Field(default="text", description="模态类型: text/image/video/voice/document")


class SaveMemoryRequest(BaseModel):
    """保存用户对话到记忆的请求"""
    user_id: str = Field(..., description="用户ID")
    user_input: str = Field(..., description="用户输入")
    assistant_response: str = Field(..., description="AI 回复")
    modality: str = Field(default="text", description="模态类型: text/image/video/voice/document")


class SaveMemoryResponse(BaseModel):
    """保存记忆的响应"""
    success: bool
    resource_id: Optional[str] = None
    category_name: Optional[str] = None
    category_id: Optional[str] = None
    importance_score: Optional[int] = None
    message: str = ""
