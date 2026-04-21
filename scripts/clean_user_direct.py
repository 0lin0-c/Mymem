"""测试数据库连接"""
import asyncio
import asyncpg


async def test():
    try:
        c = await asyncpg.connect(
            host="192.168.31.95",
            port=46195,
            user="postgres",
            password="Xzc000813!",
            database="postgres",
            ssl=False,
            timeout=30,
        )
        r = await c.fetchval("SELECT 1")
        print(f"Connection OK: {r}")

        # 查找用户
        rows = await c.fetch("SELECT id, username FROM users WHERE username = $1", "sample_0_caroline")
        if rows:
            uid = rows[0]["id"]
            print(f"Found user: {uid}")

            # 删除关联数据
            await c.execute("DELETE FROM resource_categories WHERE resource_id IN (SELECT id FROM resources WHERE user_id = $1)", uid)
            cnt_cat = await c.execute("DELETE FROM categories WHERE user_id = $1", uid)
            cnt_res = await c.execute("DELETE FROM resources WHERE user_id = $1", uid)
            cnt_usr = await c.execute("DELETE FROM users WHERE id = $1", uid)
            print(f"Deleted user {uid} and all related data")
        else:
            print("User 'sample_0_caroline' not found - already clean")

        await c.close()
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test())
