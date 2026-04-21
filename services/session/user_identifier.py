# 🆔 用户识别服务
import logging
import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.llm.base import BaseLLMProvider
from services.session.state import SessionState
from repositories import UserRepository

logger = logging.getLogger(__name__)


class UserIdentifier:
    """用户识别服务

    身份识别机制：
    - 有前端登录：用户登录后，从 JWT/Session 获取 user_id，直接绑定
    - 无前端/CLI：用户输入名字直接识别，匹配已有用户或创建新用户

    职责：
    1. LLM 引导询问用户身份
    2. 解析用户回答，匹配/创建用户
    """

    MAX_IDENTIFICATION_ATTEMPTS = 3

    def __init__(self, llm: BaseLLMProvider, session: AsyncSession):
        self.llm = llm
        self.user_repo = UserRepository(session)

    async def identify_or_ask(
        self,
        session_state: SessionState,
        user_input: str,
    ) -> dict:
        """识别用户或询问身份

        流程：
        1. 已识别 → 直接返回
        2. 超过最大询问次数 → 创建临时用户
        3. 使用 LLM 解析用户输入
        4. 匹配已有用户或创建新用户

        Returns:
            {
                "identified": bool,
                "user_id": str | None,
                "user_name": str | None,
                "response": str | None,  # 需要回复给用户的内容
            }
        """
        # 已识别，直接返回
        if session_state.is_identified:
            return {
                "identified": True,
                "user_id": session_state.user_id,
                "user_name": session_state.user_name,
                "response": None,
            }

        # 超过最大询问次数，强制创建临时用户
        if session_state.identification_attempts >= self.MAX_IDENTIFICATION_ATTEMPTS:
            user = await self.user_repo.create(
                username=f"guest_{session_state.session_id[:8]}",
                password="temp",
            )
            logger.info(f"Created temporary user: {user.username}")
            return {
                "identified": True,
                "user_id": user.id,
                "user_name": user.username,
                "response": "No problem, I've created a temporary identity for you. How can I help you today?",
            }

        # 使用 LLM 解析用户输入
        parse_result = await self._llm_parse_identification(user_input)

        if parse_result["action"] == "identified":
            user_name = parse_result["user_name"]

            # 检查是否已有此用户
            existing_user = await self.user_repo.get_by_username(user_name)

            if existing_user:
                # 已有用户，直接识别
                logger.info(f"Identified existing user: {user_name}")
                return {
                    "identified": True,
                    "user_id": existing_user.id,
                    "user_name": user_name,
                    "response": f"Welcome back, {user_name}! How can I help you today?",
                }
            else:
                # 新用户，直接创建
                user = await self.user_repo.create(
                    username=user_name,
                    password="default",
                )
                logger.info(f"Created new user: {user_name}")
                return {
                    "identified": True,
                    "user_id": user.id,
                    "user_name": user_name,
                    "response": f"Hello, {user_name}! Nice to meet you. How can I help you today?",
                }

        else:
            # 需要继续询问
            session_state.identification_attempts += 1
            return {
                "identified": False,
                "user_id": None,
                "user_name": None,
                "response": parse_result.get("response", "Hello! I'm your intelligent assistant. May I ask who you are?"),
            }

    async def _llm_parse_identification(self, user_input: str) -> dict:
        """使用 LLM 解析用户输入，判断是否回答了身份

        Returns:
            {
                "action": "identified" | "ask",
                "user_name": str | None,
                "response": str | None,
            }
        """
        prompt = self._build_parse_prompt(user_input)

        try:
            response = await self.llm.generate_chat_response(
                system_prompt="You are an identity recognition assistant that parses identity information from user input.",
                context="",
                user_query=prompt,
            )

            result = self._parse_llm_response(response)
            return result

        except Exception as e:
            logger.error(f"LLM 解析失败: {e}")
            # 降级到关键词匹配
            return self._fallback_parse(user_input)

    def _build_parse_prompt(self, user_input: str) -> str:
        """Build parse prompt"""
        return f"""Analyze the user input and determine if the user has identified themselves.

User input: {user_input}

Return JSON format:
{{
  "action": "identified" | "ask",
  "user_name": "Extracted username (if user identified themselves)",
  "response": "Question to ask if need to continue inquiring"
}}

Rules:
1. If user says "I am XXX", "My name is XXX", "Call me XXX" etc → action: "identified", user_name: XXX
2. If user says "I am a new user" → action: "identified", user_name: extracted name or generate one
3. If identity cannot be determined → action: "ask", response: friendly question

Output only JSON, no other content."""

    def _parse_llm_response(self, response: str) -> dict:
        """解析 LLM 返回的 JSON"""
        try:
            # 提取 JSON
            start = response.find("{")
            end = response.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                result = json.loads(json_str)

                # 验证并规范化
                action = result.get("action", "ask")
                if action not in ["identified", "ask"]:
                    action = "ask"

                return {
                    "action": action,
                    "user_name": result.get("user_name"),
                    "response": result.get("response"),
                }

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"LLM 响应解析失败: {e}")

        return {"action": "ask", "response": "Hello! I'm your intelligent assistant. May I ask who you are?"}

    def _fallback_parse(self, user_input: str) -> dict:
        """Fallback: keyword matching parse"""
        text = user_input.strip()

        # Check for identity declaration keywords
        keywords = ["I am", "My name is", "I'm", "Call me", "我是", "我叫", "名字是"]
        for kw in keywords:
            if kw in text:
                # Extract name
                name = text.split(kw)[-1].strip()
                # Clean up extra words
                for stop in [",", ".", "!", "?", " ", "呀", "啊", "吧"]:
                    name = name.split(stop)[0]
                if name and len(name) <= 20:
                    return {
                        "action": "identified",
                        "user_name": name,
                    }

        # Identity not recognized, return inquiry
        return {
            "action": "ask",
            "response": "Hello! I'm your intelligent assistant. May I ask who you are?",
        }

    async def _get_or_create_user(self, user_name: str):
        """根据用户名查找或创建用户"""
        # 尝试查找已有用户
        user = await self.user_repo.get_by_username(user_name)
        if user:
            return user

        # 创建新用户
        return await self.user_repo.create(
            username=user_name,
            password="default",
        )
