# 🧠 记忆管理契约：定义记忆查看、更新、删除和遗忘相关的请求/响应格式
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ========== 查询接口 ==========

class AtomicItemResponse(BaseModel):
    """原子化记忆（Category）响应项"""
    id: str = Field(..., description="原子化记忆ID")
    category_name: str = Field(..., description="所属分类名")
    content: str = Field(..., description="记忆内容")
    importance_score: int = Field(..., description="重要性分数")
    created_at: Optional[datetime] = Field(None, description="创建时间")


class ResourceResponse(BaseModel):
    """对话摘要（Resource）响应项"""
    id: str = Field(..., description="资源ID")
    modality: str = Field(..., description="模态类型")
    description: str = Field(..., description="记忆摘要")
    assistant_response: Optional[str] = Field(None, description="AI 回复")
    importance_score: int = Field(..., description="重要性分数")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    created_at: Optional[datetime] = Field(None, description="创建时间")


class ResourceDetailResponse(BaseModel):
    """对话摘要详情（含关联的原子化记忆）"""
    id: str = Field(..., description="资源ID")
    modality: str = Field(..., description="模态类型")
    raw_content: Optional[str] = Field(None, description="原始内容")
    description: str = Field(..., description="记忆摘要")
    assistant_response: Optional[str] = Field(None, description="AI 回复")
    importance_score: int = Field(..., description="重要性分数")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    atomic_items: List[AtomicItemResponse] = Field(
        default_factory=list,
        description="关联的原子化记忆列表",
    )


# ========== 管理接口请求 ==========

class DeleteMemoryRequest(BaseModel):
    """删除对话摘要请求"""
    user_id: str = Field(..., description="用户ID")
    resource_id: str = Field(..., description="资源ID")


class DeleteAtomicItemRequest(BaseModel):
    """删除原子化记忆请求"""
    user_id: str = Field(..., description="用户ID")
    item_id: str = Field(..., description="原子化记忆ID")


class UpdateMemoryRequest(BaseModel):
    """更新对话摘要请求"""
    user_id: str = Field(..., description="用户ID")
    resource_id: str = Field(..., description="资源ID")
    description: str = Field(..., description="新的摘要内容")
    importance_score: Optional[int] = Field(None, description="新的重要性分数")


class UpdateAtomicItemRequest(BaseModel):
    """更新原子化记忆请求"""
    user_id: str = Field(..., description="用户ID")
    item_id: str = Field(..., description="原子化记忆ID")
    content: str = Field(..., description="新的记忆内容")
    importance_score: Optional[int] = Field(None, description="新的重要性分数")


class ForgetRequest(BaseModel):
    """清理低重要性记忆请求"""
    user_id: str = Field(..., description="用户ID")
    threshold: float = Field(default=2.0, description="重要性阈值，低于此值的记忆将被清理")


# ========== 管理接口响应 ==========

class MemoryActionResponse(BaseModel):
    """通用操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(default="", description="操作结果说明")
