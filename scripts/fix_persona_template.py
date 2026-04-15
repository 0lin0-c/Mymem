# [临时脚本] 修复已有用户的 agent_persona_template，移除用户名和称呼指令
"""
修复 agent_persona_template：
1. "用户xxx的" → "用户的"
2. 移除 "称呼用户"xxx"，自称"xxx"。" 这行
"""
import asyncio
import sys

# Windows 编码设置
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text

from core.database import engine


async def fix_persona_templates():
    """修复所有用户的 agent_persona_template"""
    print("🔄 正在修复 agent_persona_template...")

    async with engine.begin() as conn:
        # 查找所有用户
        result = await conn.execute(text("""
            SELECT id, username, agent_persona_template
            FROM users
            WHERE agent_persona_template IS NOT NULL
        """))
        users = result.fetchall()

        if not users:
            print("✅ 没有需要修复的用户")
            return

        print(f"📋 找到 {len(users)} 个用户:")

        import re

        for user_id, username, template in users:
            if not template:
                continue

            original = template

            # 1. 替换"用户xxx的"为"用户的"
            template = re.sub(r'用户[^，。！？\s]+的', '用户的', template)

            # 2. 移除"称呼用户"xxx"，自称"xxx"。"这行
            template = re.sub(r'称呼用户"[^"]+"，自称"[^"]+"。', '', template)

            # 3. 清理多余空格
            template = re.sub(r'\s+', ' ', template).strip()

            if template != original:
                print(f"   - 用户: {username}")
                print(f"     原: {original}")
                print(f"     新: {template}")

                await conn.execute(text("""
                    UPDATE users
                    SET agent_persona_template = :template
                    WHERE id = :user_id
                """), {"template": template, "user_id": user_id})

                print(f"     ✅ 已更新")

    print("\n🎉 修复完成！")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix_persona_templates())
