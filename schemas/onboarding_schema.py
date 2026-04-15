# 📋 用户初始化契约：定义用户画像和 AI 助手定制的请求/响应格式
from typing import Optional
from pydantic import BaseModel, Field


# ========== 嵌套模型 ==========

class IdentityDetail(BaseModel):
    """身份详情（根据 identity_type 动态展示）"""
    # 学生
    education_stage: Optional[str] = Field(None, description="学段: elementary/middle/high/college/graduate")
    major: Optional[str] = Field(None, description="专业方向")
    # 上班族
    industry: Optional[str] = Field(None, description="行业")
    job_title: Optional[str] = Field(None, description="职位")
    # 教师
    subject: Optional[str] = Field(None, description="任教学科")
    teaching_stage: Optional[str] = Field(None, description="教学学段")
    # 自由职业者
    field: Optional[str] = Field(None, description="从事领域")
    # 其他
    description: Optional[str] = Field(None, description="自定义身份描述")


class AICustomization(BaseModel):
    """AI 助手定制"""
    ai_name: str = Field(..., description="AI 助手的名字", min_length=1, max_length=20)
    ai_role: str = Field(..., description="AI 身份角色: assistant/mentor/friend/advisor/partner")
    personality: list[str] = Field(default_factory=list, description="性格特点列表")
    communication_style: str = Field(default="daily", description="沟通风格: formal/casual/academic/daily")


# ========== 请求/响应 ==========

class OnboardingRequest(BaseModel):
    """用户初始化请求"""
    username: str = Field(..., description="用户名称", min_length=1, max_length=50)
    password: str = Field(..., description="登录密码", min_length=1)
    identity_type: str = Field(..., description="身份类型: student/worker/teacher/freelancer/other")
    identity_detail: Optional[IdentityDetail] = Field(default=None, description="身份详情")
    use_cases: list[str] = Field(default_factory=list, description="使用场景列表")
    interests: list[str] = Field(default_factory=list, description="兴趣标签列表")
    ai_customization: AICustomization = Field(..., description="AI 助手定制")


class CategoryItem(BaseModel):
    """分类项"""
    name: str
    description: str
    is_fixed: bool = False


class OnboardingResponse(BaseModel):
    """用户初始化响应"""
    success: bool
    user_id: Optional[str] = None
    user_prompt_template: Optional[str] = None
    agent_persona_template: Optional[str] = None
    initial_categories: Optional[dict[str, list[CategoryItem]]] = None
    message: str = ""


class ProfileUpdateRequest(BaseModel):
    """更新用户画像请求"""
    user_id: str = Field(..., description="用户ID")
    identity_type: Optional[str] = Field(None, description="身份类型")
    identity_detail: Optional[IdentityDetail] = Field(None, description="身份详情")
    use_cases: Optional[list[str]] = Field(None, description="使用场景列表")
    interests: Optional[list[str]] = Field(None, description="兴趣标签列表")


class AICustomizationUpdateRequest(BaseModel):
    """更新 AI 助手定制请求"""
    user_id: str = Field(..., description="用户ID")
    ai_name: Optional[str] = Field(None, description="AI 名字")
    ai_role: Optional[str] = Field(None, description="AI 角色")
    personality: Optional[list[str]] = Field(None, description="性格特点")
    communication_style: Optional[str] = Field(None, description="沟通风格")
