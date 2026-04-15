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
            logger.info(f"创建临时用户: {user.username}")
            return {
                "identified": True,
                "user_id": user.id,
                "user_name": user.username,
                "response": "没关系，我为你创建了一个临时身份。有什么我可以帮你的吗？",
            }

        # 使用 LLM 解析用户输入
        parse_result = await self._llm_parse_identification(user_input)

        if parse_result["action"] == "identified":
            user_name = parse_result["user_name"]

            # 检查是否已有此用户
            existing_user = await self.user_repo.get_by_username(user_name)

            if existing_user:
                # 已有用户，直接识别
                logger.info(f"识别已有用户: {user_name}")
                return {
                    "identified": True,
                    "user_id": existing_user.id,
                    "user_name": user_name,
                    "response": f"欢迎回来，{user_name}！有什么我可以帮你的吗？",
                }
            else:
                # 新用户，直接创建
                user = await self.user_repo.create(
                    username=user_name,
                    password="default",
                )
                logger.info(f"创建新用户: {user_name}")
                return {
                    "identified": True,
                    "user_id": user.id,
                    "user_name": user_name,
                    "response": f"你好，{user_name}！很高兴认识你。有什么我可以帮你的吗？",
                }

        else:
            # 需要继续询问
            session_state.identification_attempts += 1
            return {
                "identified": False,
                "user_id": None,
                "user_name": None,
                "response": parse_result.get("response", "你好！我是你的智能助手。请问你是谁呢？"),
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
                system_prompt="你是一个身份识别助手，负责解析用户输入中的身份信息。",
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
        """构建解析 prompt"""
        return f"""分析用户输入，判断用户是否表明了身份。

用户输入: {user_input}

请返回 JSON 格式：
{{
  "action": "identified" | "ask",
  "user_name": "提取的用户名（如果用户表明了身份）",
  "response": "如果需要继续询问，返回询问内容"
}}

判断规则：
1. 如果用户说"我是XXX"、"我叫XXX"、"叫我XXX"等 → action: "identified", user_name: XXX
2. 如果用户说"我是新用户" → action: "identified", user_name: 提取的名字或生成一个
3. 如果无法识别身份 → action: "ask", response: 友好的询问

只输出 JSON，不要有其他内容。"""

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

        return {"action": "ask", "response": "你好！我是你的智能助手。请问你是谁呢？"}

    def _fallback_parse(self, user_input: str) -> dict:
        """降级：关键词匹配解析"""
        text = user_input.strip()

        # 检查是否包含身份声明
        keywords = ["我是", "我叫", "我叫作", "名字是", "叫我"]
        for kw in keywords:
            if kw in text:
                # 提取名字
                name = text.split(kw)[-1].strip()
                # 清理多余的词
                for stop in ["，", "。", "！", "？", " ", "呀", "啊", "吧"]:
                    name = name.split(stop)[0]
                if name and len(name) <= 20:
                    return {
                        "action": "identified",
                        "user_name": name,
                    }

        # 未识别到身份，返回询问
        return {
            "action": "ask",
            "response": "你好！我是你的智能助手。请问你是谁呢？",
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
