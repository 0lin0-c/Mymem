# 🔐 认证契约：定义登录请求和响应格式
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名", min_length=1, max_length=50)
    password: str = Field(..., description="密码", min_length=1)


class AuthResponse(BaseModel):
    """认证响应"""
    success: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    ai_name: Optional[str] = None
    llm_configured: bool = False
    message: str = ""
