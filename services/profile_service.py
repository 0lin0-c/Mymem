import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.onboarding_schema import (
    AICustomizationUpdateRequest,
    OnboardingRequest,
    OnboardingResponse,
    ProfileUpdateRequest,
)
from services.constants import BASE_CATEGORIES
from services.llm.base import BaseLLMProvider
from services.prompts import DYNAMIC_CATEGORY_PROMPT
from repositories import CategoryRepository, ResourceRepository, UserRepository

logger = logging.getLogger(__name__)

DEFAULT_DYNAMIC_CATEGORIES = {
    "student": ["Campus Life", "Exams & Studies"],
    "worker": ["Project Development", "Career Growth"],
    "teacher": ["Teaching & Courses", "Student Management"],
    "freelancer": ["Projects & Portfolio", "Personal Brand"],
    "other": ["Life Journal", "Interest Exploration"],
}

IDENTITY_LABELS_EN = {
    "student": "student",
    "worker": "worker",
    "teacher": "teacher",
    "freelancer": "freelancer",
    "other": "other",
}

AI_ROLE_LABELS_EN = {
    "assistant": "assistant",
    "mentor": "mentor",
    "friend": "friend",
    "advisor": "advisor",
    "partner": "partner",
}

COMMUNICATION_STYLE_LABELS_EN = {
    "formal": "formal",
    "casual": "casual",
    "academic": "academic",
    "daily": "daily",
}


def build_user_prompt_template(
    *,
    username: str,
    identity_type: str,
    identity_detail: Any | None = None,
    use_cases: list[str] | None = None,
    interests: list[str] | None = None,
) -> str:
    info_lines = [f"- **Name:** {username}"]
    info_lines.append(f"- **Identity:** {IDENTITY_LABELS_EN.get(identity_type, identity_type)}")

    if identity_detail:
        detail = identity_detail
        if identity_type == "student":
            if detail.education_stage:
                info_lines.append(f"- **Education stage:** {detail.education_stage}")
            if detail.major:
                info_lines.append(f"- **Major:** {detail.major}")
        elif identity_type == "worker":
            if detail.industry:
                info_lines.append(f"- **Industry:** {detail.industry}")
            if detail.job_title:
                info_lines.append(f"- **Job title:** {detail.job_title}")
        elif identity_type == "teacher":
            if detail.subject:
                info_lines.append(f"- **Subject:** {detail.subject}")
            if getattr(detail, "teaching_stage", None):
                info_lines.append(f"- **Teaching stage:** {detail.teaching_stage}")
        elif identity_type == "freelancer":
            if detail.field:
                info_lines.append(f"- **Field:** {detail.field}")
        if getattr(detail, "description", None):
            info_lines.append(f"- **Description:** {detail.description}")

    if use_cases:
        info_lines.append(f"- **Use cases:** {', '.join(use_cases)}")

    if interests:
        info_lines.append(f"- **Interests:** {', '.join(interests)}")

    return f"""## User Profile

{chr(10).join(info_lines)}

---

## About the User

This records real user information that evolves through conversations.
You are getting to know a real person, not just building a profile."""


def build_agent_persona_template(
    *,
    ai_name: str,
    ai_role: str,
    personality: list[str] | None = None,
    communication_style: str = "daily",
) -> str:
    info_lines = [f"- **Name:** {ai_name}"]
    info_lines.append(f"- **Role:** {AI_ROLE_LABELS_EN.get(ai_role, ai_role)}")

    if personality:
        info_lines.append(f"- **Personality:** {', '.join(personality)}")

    info_lines.append(
        f"- **Communication style:** {COMMUNICATION_STYLE_LABELS_EN.get(communication_style, communication_style)}"
    )

    return f"""## AI Assistant Profile

{chr(10).join(info_lines)}

---

This is your persona. Maintain consistent style when communicating with the user.

**Note:** Answer questions directly. No need to address the user by name every time, except on first greeting."""


class ProfileService:
    def __init__(self, session: AsyncSession, llm: BaseLLMProvider):
        self.session = session
        self.llm = llm
        self.user_repo = UserRepository(session)
        self.category_repo = CategoryRepository(session)
        self.resource_repo = ResourceRepository(session)

    async def onboarding(self, request: OnboardingRequest) -> OnboardingResponse:
        try:
            existing_user = await self.user_repo.get_by_username(request.username)
            if existing_user:
                return OnboardingResponse(
                    success=False,
                    message="Username already exists, please choose another one or log in directly.",
                )

            user_prompt_template = self._generate_user_prompt_template(request)
            agent_persona_template = self._generate_agent_persona_template(request)

            user = await self.user_repo.create(
                username=request.username,
                password=request.password,
                user_prompt_template=user_prompt_template,
                agent_persona_template=agent_persona_template,
            )
            user_id = user.id

            if self._is_llm_available():
                dynamic_category_names = await self._generate_dynamic_categories(request)
                logger.info("LLM generated dynamic categories: %s", dynamic_category_names)
            else:
                dynamic_category_names = self._get_default_dynamic_categories(request.identity_type)
                logger.info("Using default dynamic categories: %s", dynamic_category_names)

            await self._store_initial_profile(user_id, request, dynamic_category_names)
            await self.session.commit()

            return OnboardingResponse(
                success=True,
                user_id=user_id,
                user_prompt_template=user_prompt_template,
                agent_persona_template=agent_persona_template,
                initial_categories={
                    "fixed": [
                        {"name": c["name"], "description": c["description"], "is_fixed": True}
                        for c in BASE_CATEGORIES
                    ],
                    "dynamic": [
                        {
                            "name": name,
                            "description": f"User-specific memories related to {name}",
                            "is_fixed": False,
                        }
                        for name in dynamic_category_names
                    ],
                },
                message="Onboarding completed. You can start chatting now.",
            )
        except Exception as exc:
            await self.session.rollback()
            logger.error("Onboarding failed: %s", exc)
            return OnboardingResponse(
                success=False,
                message=f"Onboarding failed: {exc}",
            )

    def _is_llm_available(self) -> bool:
        from core.config import settings

        if settings.openai_api_key or settings.anthropic_api_key:
            return True
        return False

    def _get_default_dynamic_categories(self, identity_type: str) -> list[str]:
        return DEFAULT_DYNAMIC_CATEGORIES.get(identity_type, DEFAULT_DYNAMIC_CATEGORIES["other"])

    async def _generate_dynamic_categories(self, request: OnboardingRequest) -> list[str]:
        user_profile = self._build_user_profile(request)
        prompt = DYNAMIC_CATEGORY_PROMPT.format(user_profile=user_profile)

        try:
            response = await self.llm.generate_chat_response(
                system_prompt=(
                    "You are a memory classification expert. Generate personalized "
                    "memory category names based on user profile."
                ),
                context="",
                user_query=prompt,
            )
            categories = self._parse_dynamic_categories_response(response)
            if len(categories) >= 2:
                return categories[:2]
            logger.warning("LLM returned too few dynamic categories: %s", categories)
        except Exception as exc:
            logger.error("LLM failed to generate dynamic categories: %s", exc)
        return self._get_default_dynamic_categories(request.identity_type)

    def _build_user_profile(self, request: OnboardingRequest) -> str:
        lines = [f"- Identity: {request.identity_type}"]

        if request.identity_detail:
            detail = request.identity_detail
            if request.identity_type == "student":
                if detail.education_stage:
                    lines.append(f"- Education stage: {detail.education_stage}")
                if detail.major:
                    lines.append(f"- Major: {detail.major}")
            elif request.identity_type == "worker":
                if detail.industry:
                    lines.append(f"- Industry: {detail.industry}")
                if detail.job_title:
                    lines.append(f"- Job title: {detail.job_title}")
            elif request.identity_type == "teacher":
                if detail.subject:
                    lines.append(f"- Subject: {detail.subject}")
                if getattr(detail, "teaching_stage", None):
                    lines.append(f"- Teaching stage: {detail.teaching_stage}")
            elif request.identity_type == "freelancer":
                if detail.field:
                    lines.append(f"- Field: {detail.field}")
            if getattr(detail, "description", None):
                lines.append(f"- Description: {detail.description}")

        if request.use_cases:
            lines.append(f"- Use cases: {', '.join(request.use_cases)}")

        if request.interests:
            lines.append(f"- Interests: {', '.join(request.interests)}")

        return "\n".join(lines)

    def _parse_dynamic_categories_response(self, response: str) -> list[str]:
        import re

        try:
            data = json.loads(response)
            if isinstance(data, dict) and "dynamic_categories" in data:
                return [c.get("name", "") for c in data["dynamic_categories"] if c.get("name")]
            if isinstance(data, list):
                return [c.get("name", c) if isinstance(c, dict) else c for c in data]
        except json.JSONDecodeError:
            pass

        match = re.search(r"\[[\s\S]*?\]", response)
        if match:
            try:
                data = json.loads(match.group())
                return [c.get("name", c) if isinstance(c, dict) else c for c in data]
            except json.JSONDecodeError:
                pass
        return []

    def _generate_user_prompt_template(self, request: OnboardingRequest) -> str:
        return build_user_prompt_template(
            username=request.username,
            identity_type=request.identity_type,
            identity_detail=request.identity_detail,
            use_cases=request.use_cases,
            interests=request.interests,
        )

    def _generate_agent_persona_template(self, request: OnboardingRequest) -> str:
        ai = request.ai_customization
        return build_agent_persona_template(
            ai_name=ai.ai_name,
            ai_role=ai.ai_role,
            personality=ai.personality,
            communication_style=ai.communication_style,
        )

    async def _store_initial_profile(
        self,
        user_id: str,
        request: OnboardingRequest,
        dynamic_category_names: list[str],
    ) -> None:
        items_to_create = []

        items_to_create.append(
            {
                "category_name": "Core Self",
                "content": f"User's name is {request.username}",
                "importance_score": 3,
            }
        )

        identity_label = IDENTITY_LABELS_EN.get(request.identity_type, request.identity_type)
        items_to_create.append(
            {
                "category_name": "Core Self",
                "content": f"User identity type is {identity_label}",
                "importance_score": 3,
            }
        )

        if request.interests:
            for interest in request.interests:
                items_to_create.append(
                    {
                        "category_name": "Core Self",
                        "content": f"User is interested in {interest}",
                        "importance_score": 2,
                    }
                )

        if request.use_cases:
            for use_case in request.use_cases:
                items_to_create.append(
                    {
                        "category_name": "Core Self",
                        "content": f"User's use case includes {use_case}",
                        "importance_score": 1,
                    }
                )

        if dynamic_category_names:
            for dyn_name in dynamic_category_names:
                items_to_create.append(
                    {
                        "category_name": dyn_name,
                        "content": f'User has a dedicated dynamic category "{dyn_name}" for related memories',
                        "importance_score": 2,
                    }
                )

        for item in items_to_create:
            try:
                item["content_vector"] = await self.llm.get_embedding(item["content"])
            except Exception as exc:
                logger.warning("Failed to generate vector: %s, content=%s", exc, item["content"][:50])
                item["content_vector"] = None

        await self.category_repo.create_items_batch(user_id, items_to_create)

    async def update_profile(self, request: ProfileUpdateRequest) -> dict:
        user = await self.user_repo.get_by_id(request.user_id)
        if not user:
            return {"success": False, "message": "User not found"}

        new_template = build_user_prompt_template(
            username=user.username,
            identity_type=request.identity_type or "other",
            identity_detail=request.identity_detail,
            use_cases=request.use_cases,
            interests=request.interests,
        )
        await self.user_repo.update(request.user_id, user_prompt_template=new_template)

        await self.session.commit()
        return {"success": True, "message": "User profile updated"}

    async def update_ai_customization(self, request: AICustomizationUpdateRequest) -> dict:
        user = await self.user_repo.get_by_id(request.user_id)
        if not user:
            return {"success": False, "message": "User not found"}

        new_template = build_agent_persona_template(
            ai_name=request.ai_name or "Assistant",
            ai_role=request.ai_role or "assistant",
            personality=request.personality,
            communication_style=request.communication_style or "daily",
        )
        await self.user_repo.update(request.user_id, agent_persona_template=new_template)

        await self.session.commit()
        return {"success": True, "message": "AI customization updated"}

    def get_all_category_names(self, dynamic_names: list[str]) -> list[str]:
        return [c["name"] for c in BASE_CATEGORIES] + dynamic_names
