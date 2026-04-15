# 🧠 用户资产服务：处理冷启动初始化
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.onboarding_schema import (
    OnboardingRequest,
    OnboardingResponse,
    ProfileUpdateRequest,
    AICustomizationUpdateRequest,
)
from services.llm.base import BaseLLMProvider
from services.prompts import DYNAMIC_CATEGORY_PROMPT
from services.constants import BASE_CATEGORIES
from repositories import UserRepository, CategoryRepository, ResourceRepository

logger = logging.getLogger(__name__)

# 默认动态分类映射（当 LLM 不可用时使用）
DEFAULT_DYNAMIC_CATEGORIES = {
    "student": ["学校生活", "考试与升学"],
    "worker": ["项目研发", "职业发展"],
    "teacher": ["教学教务", "学生管理"],
    "freelancer": ["项目作品", "个人品牌"],
    "other": ["生活记录", "兴趣探索"],
}


class ProfileService:
    """用户画像与 AI 助手定制服务

    职责：
    1. 生成 user_prompt_template（精简版，每次对话加载）
    2. 生成 agent_persona_template（AI 人设）
    3. 将初始化信息作为原子化记忆存入 Category 表（含向量）
    4. 动态分类生成（混合方案：LLM 可用时立即生成，不可用时延后）
    """

    def __init__(self, session: AsyncSession, llm: BaseLLMProvider):
        self.session = session
        self.llm = llm
        self.user_repo = UserRepository(session)
        self.category_repo = CategoryRepository(session)
        self.resource_repo = ResourceRepository(session)

    async def onboarding(self, request: OnboardingRequest) -> OnboardingResponse:
        """用户初始化流程

        动态分类生成策略：
        - LLM 可用 → 调用 LLM 生成个性化分类
        - LLM 不可用 → 使用默认分类或占位符
        """
        try:
            # ========== Step 0: 检查用户名是否已存在 ==========
            existing_user = await self.user_repo.get_by_username(request.username)
            if existing_user:
                return OnboardingResponse(
                    success=False,
                    message="用户名已存在，请更换或直接登录",
                )

            # ========== Step 1: 生成模板 ==========
            user_prompt_template = self._generate_user_prompt_template(request)
            agent_persona_template = self._generate_agent_persona_template(request)

            # ========== Step 2: 创建用户（一次性写入所有字段） ==========
            user = await self.user_repo.create(
                username=request.username,
                password=request.password,
                user_prompt_template=user_prompt_template,
                agent_persona_template=agent_persona_template,
            )
            user_id = user.id

            # ========== Step 3: 动态分类生成（混合方案） ==========
            if self._is_llm_available():
                # LLM 可用，立即生成个性化分类
                dynamic_category_names = await self._generate_dynamic_categories(request)
                logger.info(f"LLM 生成动态分类: {dynamic_category_names}")
            else:
                # LLM 不可用，使用默认分类
                dynamic_category_names = self._get_default_dynamic_categories(request.identity_type)
                logger.info(f"使用默认动态分类: {dynamic_category_names}")

            # ========== Step 4: 将用户初始化信息存入 Category 表 ==========
            await self._store_initial_profile(user_id, request, dynamic_category_names)

            # ========== Step 5: 提交事务 ==========
            await self.session.commit()

            # 构建返回的分类列表（用于显示）
            all_categories = [
                {"name": c["name"], "description": c["description"]}
                for c in BASE_CATEGORIES
            ] + [
                {"name": name, "description": f"用户专属的{name}相关记忆"}
                for name in dynamic_category_names
            ]

            return OnboardingResponse(
                success=True,
                user_id=user_id,
                user_prompt_template=user_prompt_template,
                agent_persona_template=agent_persona_template,
                initial_categories={
                    "fixed": [{"name": c["name"], "description": c["description"], "is_fixed": True} for c in BASE_CATEGORIES],
                    "dynamic": [{"name": name, "description": f"用户专属的{name}相关记忆", "is_fixed": False} for name in dynamic_category_names],
                },
                message="身份初始化完成，可以开始对话了",
            )

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Onboarding 失败: {e}")
            return OnboardingResponse(
                success=False,
                message=f"初始化失败: {str(e)}",
            )

    def _is_llm_available(self) -> bool:
        """判断 LLM 是否可用

        判断逻辑：
        1. 服务端全局配置：检查 Settings 中是否配置了 API Key
        2. 用户级配置：检查用户是否设置了自己的 API Key（未来扩展）
        """
        from core.config import settings

        # 服务端全局 LLM 配置
        if settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY:
            return True

        # TODO: 用户级 LLM 配置（未来扩展）
        # if user.llm_config and user.llm_config.api_key:
        #     return True

        return False

    def _get_default_dynamic_categories(self, identity_type: str) -> list[str]:
        """获取默认动态分类（当 LLM 不可用时使用）

        根据用户身份类型返回预设的默认分类。

        Args:
            identity_type: 身份类型（student/worker/teacher/freelancer/other）

        Returns:
            2 个动态分类名称列表
        """
        return DEFAULT_DYNAMIC_CATEGORIES.get(identity_type, DEFAULT_DYNAMIC_CATEGORIES["other"])

    async def _generate_dynamic_categories(self, request: OnboardingRequest) -> list[str]:
        """调用 LLM 生成个性化动态分类

        Args:
            request: 初始化请求

        Returns:
            2 个动态分类名称列表
        """
        # 构建用户画像
        user_profile = self._build_user_profile(request)
        prompt = DYNAMIC_CATEGORY_PROMPT.format(user_profile=user_profile)

        try:
            response = await self.llm.generate_chat_response(
                system_prompt="你是一个记忆分类专家。请根据用户画像生成个性化的记忆分类名称。",
                context="",
                user_query=prompt,
            )

            # 解析 LLM 返回的分类
            categories = self._parse_dynamic_categories_response(response)

            if len(categories) >= 2:
                return categories[:2]
            else:
                # 解析失败，使用默认分类
                logger.warning(f"LLM 返回分类数量不足: {categories}")
                return self._get_default_dynamic_categories(request.identity_type)

        except Exception as e:
            logger.error(f"LLM 生成动态分类失败: {e}")
            return self._get_default_dynamic_categories(request.identity_type)

    def _build_user_profile(self, request: OnboardingRequest) -> str:
        """构建用户画像字符串（用于 LLM prompt）"""
        identity_map = {
            "student": "学生",
            "worker": "上班族",
            "teacher": "教师",
            "freelancer": "自由职业者",
            "other": "其他",
        }

        lines = [f"- 身份：{identity_map.get(request.identity_type, request.identity_type)}"]

        if request.identity_detail:
            detail = request.identity_detail
            if request.identity_type == "student":
                if detail.education_stage:
                    stage_map = {"elementary": "小学", "middle": "初中", "high": "高中", "college": "大学", "graduate": "研究生"}
                    lines.append(f"- 学段：{stage_map.get(detail.education_stage, detail.education_stage)}")
                if detail.major:
                    lines.append(f"- 专业方向：{detail.major}")
            elif request.identity_type == "worker":
                if detail.industry:
                    lines.append(f"- 行业：{detail.industry}")
                if detail.job_title:
                    lines.append(f"- 职位：{detail.job_title}")
            elif request.identity_type == "teacher":
                if detail.subject:
                    lines.append(f"- 任教学科：{detail.subject}")
            elif request.identity_type == "freelancer":
                if detail.field:
                    lines.append(f"- 从事领域：{detail.field}")

        if request.use_cases:
            lines.append(f"- 使用场景：{', '.join(request.use_cases)}")

        if request.interests:
            lines.append(f"- 兴趣标签：{', '.join(request.interests)}")

        return "\n".join(lines)

    def _parse_dynamic_categories_response(self, response: str) -> list[str]:
        """解析 LLM 返回的动态分类"""
        import re

        try:
            data = json.loads(response)
            if isinstance(data, dict) and "dynamic_categories" in data:
                categories = data["dynamic_categories"]
                return [c.get("name", "") for c in categories if c.get("name")]
            if isinstance(data, list):
                return [c.get("name", c) if isinstance(c, dict) else c for c in data]
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 数组
        match = re.search(r'\[[\s\S]*?\]', response)
        if match:
            try:
                data = json.loads(match.group())
                return [c.get("name", c) if isinstance(c, dict) else c for c in data]
            except json.JSONDecodeError:
                pass

        return []

    def _generate_user_prompt_template(self, request: OnboardingRequest) -> str:
        """生成 user_prompt_template（用户画像）"""
        identity_map = {
            "student": "学生",
            "worker": "上班族",
            "teacher": "教师",
            "freelancer": "自由职业者",
            "other": "其他",
        }
        identity_cn = identity_map.get(request.identity_type, request.identity_type)

        # 构建信息列表
        info_lines = [f"- **称呼:** {request.username}"]
        info_lines.append(f"- **身份:** {identity_cn}")

        # 身份详情
        if request.identity_detail:
            detail = request.identity_detail
            if request.identity_type == "student":
                if detail.education_stage:
                    stage_map = {
                        "elementary": "小学",
                        "middle": "初中",
                        "high": "高中",
                        "college": "大学",
                        "graduate": "研究生",
                    }
                    info_lines.append(f"- **学段:** {stage_map.get(detail.education_stage, detail.education_stage)}")
                if detail.major:
                    info_lines.append(f"- **专业方向:** {detail.major}")
            elif request.identity_type == "worker":
                if detail.industry:
                    info_lines.append(f"- **行业:** {detail.industry}")
                if detail.job_title:
                    info_lines.append(f"- **职位:** {detail.job_title}")
            elif request.identity_type == "teacher":
                if detail.subject:
                    info_lines.append(f"- **任教学科:** {detail.subject}")
            elif request.identity_type == "freelancer":
                if detail.field:
                    info_lines.append(f"- **从事领域:** {detail.field}")

        # 使用场景
        if request.use_cases:
            info_lines.append(f"- **使用场景:** {', '.join(request.use_cases)}")

        # 兴趣
        if request.interests:
            info_lines.append(f"- **兴趣:** {', '.join(request.interests)}")

        # 组装模板
        template = f"""## 用户信息

{chr(10).join(info_lines)}

---

## 关于用户

这里记录的是用户的真实信息，随着交流深入会不断丰富。
你是在了解一个真实的人，而不是在建立档案。"""
        return template

    def _generate_agent_persona_template(self, request: OnboardingRequest) -> str:
        """生成 agent_persona_template（助手人设）"""
        ai = request.ai_customization

        role_map = {
            "assistant": "助手",
            "mentor": "导师",
            "friend": "朋友",
            "advisor": "顾问",
            "partner": "伙伴",
        }
        role_cn = role_map.get(ai.ai_role, ai.ai_role)

        # 构建信息列表
        info_lines = [f"- **名称:** {ai.ai_name}"]
        info_lines.append(f"- **角色:** {role_cn}")

        if ai.personality:
            info_lines.append(f"- **性格:** {'、'.join(ai.personality)}")

        style_map = {
            "formal": "正式严谨",
            "casual": "轻松随意",
            "academic": "学术专业",
            "daily": "日常轻松",
        }
        style_cn = style_map.get(ai.communication_style, ai.communication_style)
        info_lines.append(f"- **沟通风格:** {style_cn}")

        # 组装模板
        template = f"""## 助手信息

{chr(10).join(info_lines)}

---

这是你的身份设定。请保持一致的风格与用户交流。

**提示:** 直接回答问题，不需要每次都称呼用户。仅在用户首次问候时可以称呼。"""
        return template

    async def _store_initial_profile(
        self,
        user_id: str,
        request: OnboardingRequest,
        dynamic_category_names: list[str],
    ) -> None:
        """将用户初始化信息作为原子化记忆存入 Category 表（含向量）"""
        items_to_create = []

        # 姓名存入核心自我
        items_to_create.append({
            "category_name": "核心自我",
            "content": f"用户姓名是{request.username}",
            "importance_score": 10,
        })

        # 身份信息存入核心自我
        identity_map = {
            "student": "学生",
            "worker": "上班族",
            "teacher": "教师",
            "freelancer": "自由职业者",
            "other": "其他",
        }
        identity_cn = identity_map.get(request.identity_type, request.identity_type)
        items_to_create.append({
            "category_name": "核心自我",
            "content": f"用户身份是{identity_cn}",
            "importance_score": 9,
        })

        # 兴趣存入核心自我
        if request.interests:
            for interest in request.interests:
                items_to_create.append({
                    "category_name": "核心自我",
                    "content": f"用户对{interest}感兴趣",
                    "importance_score": 7,
                })

        # 使用场景存入核心自我
        if request.use_cases:
            for use_case in request.use_cases:
                items_to_create.append({
                    "category_name": "核心自我",
                    "content": f"用户的使用场景包括{use_case}",
                    "importance_score": 6,
                })

        # 为每个 item 生成向量
        for item in items_to_create:
            try:
                item["content_vector"] = await self.llm.get_embedding(item["content"])
            except Exception as e:
                logger.warning(f"生成向量失败: {e}, content={item['content'][:50]}")
                item["content_vector"] = None

        # 批量创建（初始化时不创建 Resource，直接创建原子化记忆）
        await self.category_repo.create_items_batch(user_id, items_to_create)

    async def update_profile(self, request: ProfileUpdateRequest) -> dict:
        """更新用户画像

        根据请求中提供的字段重新生成 user_prompt_template 并更新。
        """
        user = await self.user_repo.get_by_id(request.user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 构建更新后的画像文本
        parts = [f"用户{user.username}"]
        identity_map = {
            "student": "学生", "worker": "上班族", "teacher": "教师",
            "freelancer": "自由职业者", "other": "其他",
        }
        if request.identity_type:
            parts.append(identity_map.get(request.identity_type, request.identity_type))
        if request.identity_detail:
            detail = request.identity_detail
            for val in [detail.education_stage, detail.major, detail.industry,
                        detail.job_title, detail.subject, detail.field, detail.description]:
                if val:
                    parts.append(val)
        if request.interests:
            parts.append(f"兴趣：{'、'.join(request.interests)}")

        new_template = "，".join(parts) + "。"
        await self.user_repo.update(request.user_id, user_prompt_template=new_template)

        await self.session.commit()
        return {"success": True, "message": "用户画像已更新"}

    async def update_ai_customization(self, request: AICustomizationUpdateRequest) -> dict:
        """更新 AI 助手定制

        根据请求中提供的字段重新生成 agent_persona_template 并更新。
        """
        user = await self.user_repo.get_by_id(request.user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 基于现有模板增量更新
        role_map = {
            "assistant": "助手", "mentor": "导师", "friend": "朋友",
            "advisor": "顾问", "partner": "伙伴",
        }
        parts = []
        if request.ai_name:
            role_cn = role_map.get(request.ai_role, request.ai_role) if request.ai_role else "助手"
            parts.append(f"你是{request.ai_name}，用户{user.username}的{role_cn}。")
        if request.personality:
            parts.append(f"性格：{'、'.join(request.personality)}。")
        if request.communication_style:
            style_map = {"formal": "正式严谨", "casual": "轻松随意",
                         "academic": "学术专业", "daily": "日常轻松"}
            parts.append(f"沟通风格：{style_map.get(request.communication_style, request.communication_style)}。")

        if parts:
            new_template = "".join(parts)
            await self.user_repo.update(request.user_id, agent_persona_template=new_template)

        await self.session.commit()
        return {"success": True, "message": "AI 助手定制已更新"}

    def get_all_category_names(self, dynamic_names: list[str]) -> list[str]:
        """获取所有 6 个分类名称"""
        return [c["name"] for c in BASE_CATEGORIES] + dynamic_names
