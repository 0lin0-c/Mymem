import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.database import engine
from services.profile_service import build_agent_persona_template, build_user_prompt_template


ZH_IDENTITY_MAP = {
    "学生": "student",
    "上班族": "worker",
    "教师": "teacher",
    "自由职业者": "freelancer",
    "其他": "other",
}

ZH_ROLE_MAP = {
    "助手": "assistant",
    "导师": "mentor",
    "朋友": "friend",
    "顾问": "advisor",
    "伙伴": "partner",
}

ZH_STYLE_MAP = {
    "正式严谨": "formal",
    "轻松随意": "casual",
    "学术专业": "academic",
    "日常轻松": "daily",
}


@dataclass
class TemplateFix:
    user_id: str
    username: str
    user_prompt_template: str | None = None
    agent_persona_template: str | None = None


def _contains_cjk(text_value: str | None) -> bool:
    if not text_value:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", text_value))


def _detect_identity_type(text_value: str | None) -> str:
    content = text_value or ""
    for zh_label, en_label in ZH_IDENTITY_MAP.items():
        if zh_label in content:
            return en_label
    match = re.search(r"- \*\*Identity:\*\* ([^\n]+)", content)
    if match:
        return match.group(1).strip().lower()
    return "other"


def _extract_interests(text_value: str | None) -> list[str]:
    if not text_value:
        return []
    for pattern in [
        r"兴趣[:：]\s*([^\n。]+)",
        r"- \*\*Interests:\*\* ([^\n]+)",
    ]:
        match = re.search(pattern, text_value)
        if match:
            return [item.strip() for item in re.split(r"[，,、;；]", match.group(1)) if item.strip()]
    return []


def _extract_use_cases(text_value: str | None) -> list[str]:
    if not text_value:
        return []
    for pattern in [
        r"使用场景[:：]\s*([^\n。]+)",
        r"- \*\*Use cases:\*\* ([^\n]+)",
    ]:
        match = re.search(pattern, text_value)
        if match:
            return [item.strip() for item in re.split(r"[，,、;；]", match.group(1)) if item.strip()]
    return []


def _extract_ai_name(text_value: str | None) -> str:
    if not text_value:
        return "Assistant"
    for pattern in [
        r"你是([^，。,]+)",
        r"- \*\*Name:\*\* ([^\n]+)",
    ]:
        match = re.search(pattern, text_value)
        if match:
            return match.group(1).strip()
    return "Assistant"


def _extract_ai_role(text_value: str | None) -> str:
    if not text_value:
        return "assistant"
    for zh_label, en_label in ZH_ROLE_MAP.items():
        if zh_label in text_value:
            return en_label
    match = re.search(r"- \*\*Role:\*\* ([^\n]+)", text_value)
    if match:
        return match.group(1).strip().lower()
    return "assistant"


def _extract_personality(text_value: str | None) -> list[str]:
    if not text_value:
        return []
    for pattern in [
        r"性格[:：]\s*([^\n。]+)",
        r"- \*\*Personality:\*\* ([^\n]+)",
    ]:
        match = re.search(pattern, text_value)
        if match:
            return [item.strip() for item in re.split(r"[，,、;；]", match.group(1)) if item.strip()]
    return []


def _extract_style(text_value: str | None) -> str:
    if not text_value:
        return "daily"
    for zh_label, en_label in ZH_STYLE_MAP.items():
        if zh_label in text_value:
            return en_label
    match = re.search(r"- \*\*Communication style:\*\* ([^\n]+)", text_value)
    if match:
        return match.group(1).strip().lower()
    return "daily"


def _build_fixed_templates(
    *,
    username: str,
    user_prompt_template: str | None,
    agent_persona_template: str | None,
) -> TemplateFix | None:
    fix = TemplateFix(user_id="", username=username)
    if user_prompt_template and _contains_cjk(user_prompt_template):
        fix.user_prompt_template = build_user_prompt_template(
            username=username,
            identity_type=_detect_identity_type(user_prompt_template),
            use_cases=_extract_use_cases(user_prompt_template),
            interests=_extract_interests(user_prompt_template),
        )
    if agent_persona_template and _contains_cjk(agent_persona_template):
        fix.agent_persona_template = build_agent_persona_template(
            ai_name=_extract_ai_name(agent_persona_template),
            ai_role=_extract_ai_role(agent_persona_template),
            personality=_extract_personality(agent_persona_template),
            communication_style=_extract_style(agent_persona_template),
        )
    if fix.user_prompt_template or fix.agent_persona_template:
        return fix
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Chinese user templates in the users table.")
    parser.add_argument("--apply", action="store_true", help="Actually update the database.")
    args = parser.parse_args()

    scanned = 0
    pending: list[TemplateFix] = []

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT id, username, user_prompt_template, agent_persona_template
                FROM users
                ORDER BY created_at ASC
                """
            )
        )
        rows = result.fetchall()
        scanned = len(rows)

        for user_id, username, user_prompt_template, agent_persona_template in rows:
            fix = _build_fixed_templates(
                username=username,
                user_prompt_template=user_prompt_template,
                agent_persona_template=agent_persona_template,
            )
            if not fix:
                continue
            fix.user_id = user_id
            pending.append(fix)

        print(f"Scanned users: {scanned}")
        print(f"Users needing template fixes: {len(pending)}")
        for fix in pending:
            changed_fields = []
            if fix.user_prompt_template:
                changed_fields.append("user_prompt_template")
            if fix.agent_persona_template:
                changed_fields.append("agent_persona_template")
            print(f"- {fix.username}: {', '.join(changed_fields)}")

        if not args.apply:
            print("Dry run complete. Re-run with --apply to write changes.")
            return

        updated = 0
        for fix in pending:
            updates = {}
            if fix.user_prompt_template:
                updates["user_prompt_template"] = fix.user_prompt_template
            if fix.agent_persona_template:
                updates["agent_persona_template"] = fix.agent_persona_template
            if not updates:
                continue
            await conn.execute(
                text(
                    """
                    UPDATE users
                    SET user_prompt_template = COALESCE(:user_prompt_template, user_prompt_template),
                        agent_persona_template = COALESCE(:agent_persona_template, agent_persona_template)
                    WHERE id = :user_id
                    """
                ),
                {
                    "user_id": fix.user_id,
                    "user_prompt_template": updates.get("user_prompt_template"),
                    "agent_persona_template": updates.get("agent_persona_template"),
                },
            )
            updated += 1

        print(f"Updated users: {updated}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
