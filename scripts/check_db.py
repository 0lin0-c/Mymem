"""快速检查数据库中的数据状态"""
import asyncio
from core.database import AsyncSessionLocal
from sqlalchemy import text


async def check():
    async with AsyncSessionLocal() as s:
        # 表行数
        for table in ["users", "resources", "categories", "resource_categories"]:
            r = await s.execute(text(f"SELECT count(*) FROM {table}"))
            print(f"{table}: {r.scalar()} rows")

        # 用户详情
        r = await s.execute(text("SELECT id, username FROM users"))
        print(f"\nuser details: {r.fetchall()}")

        # resources 按 user_id
        r = await s.execute(text("SELECT user_id, count(*) FROM resources GROUP BY user_id"))
        print(f"resources by user: {r.fetchall()}")

        # categories 按 user_id
        r = await s.execute(text("SELECT user_id, count(*) FROM categories GROUP BY user_id"))
        print(f"categories by user: {r.fetchall()}")

        # 向量维度检查
        r = await s.execute(text(
            "SELECT user_id, array_length(description_vector, 1) as dim FROM resources LIMIT 3"
        ))
        print(f"resource vector dims: {r.fetchall()}")

        r = await s.execute(text(
            "SELECT user_id, array_length(content_vector, 1) as dim FROM categories LIMIT 3"
        ))
        print(f"category vector dims: {r.fetchall()}")


if __name__ == "__main__":
    asyncio.run(check())
