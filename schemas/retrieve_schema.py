# 🔍 检索契约：定义检索相关的请求体与响应体格式。
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    """检索请求"""
    user_id: str = Field(..., description="用户ID")
    query: str = Field(..., description="用户查询")
    top_k: int = Field(default=10, description="返回数量")
    min_importance: int = Field(default=3, description="最低重要性过滤")


class RetrieveResultItem(BaseModel):
    """单条检索结果"""
    resource_id: str = Field(..., description="资源ID")
    description: str = Field(..., description="记忆内容摘要")
    category_name: Optional[str] = Field(None, description="所属分类名")
    importance_score: int = Field(..., description="重要性分数")
    retrieval_score: float = Field(..., description="检索分数")
    created_at: Optional[datetime] = Field(None, description="创建时间")


class RetrieveResponse(BaseModel):
    """检索响应"""
    categories_detected: List[str] = Field(
        default_factory=list,
        description="LLM 检测到的相关分类",
    )
    results: List[RetrieveResultItem] = Field(
        default_factory=list,
        description="检索结果列表",
    )
    total: int = Field(default=0, description="结果总数")
    context_text: str = Field(default="", description="构建的上下文文本")


class RetrieveStatsResponse(BaseModel):
    """检索统计响应"""
    total_retrievals: int = Field(default=0, description="总检索次数")
    avg_results_per_query: float = Field(default=0.0, description="平均每次查询返回结果数")
    category_distribution: dict = Field(
        default_factory=dict,
        description="各分类的命中分布",
    )
    avg_latency_ms: float = Field(default=0.0, description="平均检索延迟(ms)")
