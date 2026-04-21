"""清理指定用户的全部数据"""
import asyncio
import sys
sys.path.insert(0, ".")
from core.database import AsyncSessionLocal
from sqlalchemy import text


async def clean(username: str):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            # 查找用户
            r = await s.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username})
            row = r.fetchone()
            if not row:
                print(f"User '{username}' not found")
                return
            uid = str(row[0])
            print(f"Found user: {uid}")

            # 删除关联数据（按依赖顺序）
            await s.execute(text(
                "DELETE FROM resource_categories WHERE resource_id IN "
                "(SELECT id FROM resources WHERE user_id = :uid)"), {"uid": uid})
            await s.execute(text("DELETE FROM categories WHERE user_id = :uid"), {"uid": uid})
            await s.execute(text("DELETE FROM resources WHERE user_id = :uid"), {"uid": uid})
            await s.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
            print(f"Deleted all data for user '{username}' ({uid})")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample_0_caroline"
    asyncio.run(clean(target))
