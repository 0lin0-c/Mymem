# 查询数据库中最新插入的测试数据
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from core.config import settings


async def query_latest_data():
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        print("=" * 60)
        print("📊 数据库最新数据查询")
        print("=" * 60)

        # 1. 查询 users 表
        print("\n👤 users 表 (最新3条):")
        result = await conn.execute(text(
            "SELECT id, username, created_at FROM users ORDER BY created_at DESC LIMIT 3"
        ))
        for row in result:
            print(f"  ID: {row[0]}")
            print(f"  username: {row[1]}")
            print(f"  created_at: {row[2]}")
            print()

        # 2. 查询 categories 表
        print("\n🧠 categories 表 (最新3条):")
        result = await conn.execute(text("""
            SELECT c.id, c.category_name, c.content_summary,
                   c.importance_score, c.is_fixed, c.created_at,
                   u.username
            FROM categories c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.created_at DESC LIMIT 3
        """))
        for row in result:
            print(f"  ID: {row[0]}")
            print(f"  category_name: {row[1]}")
            print(f"  content_summary: {row[2]}")
            print(f"  importance_score: {row[3]}")
            print(f"  is_fixed: {row[4]}")
            print(f"  username: {row[6]}")
            print()

        # 3. 查询 resources 表
        print("\n📦 resources 表 (最新3条):")
        result = await conn.execute(text("""
            SELECT r.id, r.raw_content, r.description,
                   r.importance_score, length(r.description_vector) as vec_len,
                   r.created_at, u.username
            FROM resources r
            JOIN users u ON r.user_id = u.id
            ORDER BY r.created_at DESC LIMIT 3
        """))
        for row in result:
            print(f"  ID: {row[0]}")
            print(f"  raw_content: {row[1][:80]}...")
            print(f"  description: {row[2]}")
            print(f"  importance_score: {row[3]}")
            print(f"  vector_length: {row[4]} bytes")
            print(f"  username: {row[6]}")
            print()

        # 4. 查询 resource_categories 表
        print("\n🔗 resource_categories 表 (最新3条):")
        result = await conn.execute(text("""
            SELECT rc.id, rc.resource_id, rc.category_id,
                   c.category_name, r.raw_content,
                   rc.created_at
            FROM resource_categories rc
            JOIN categories c ON rc.category_id = c.id
            JOIN resources r ON rc.resource_id = r.id
            ORDER BY rc.created_at DESC LIMIT 3
        """))
        for row in result:
            print(f"  ID: {row[0]}")
            print(f"  resource_id: {row[1]}")
            print(f"  category_id: {row[2]}")
            print(f"  category_name: {row[3]}")
            print(f"  resource_preview: {row[4][:50]}...")
            print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(query_latest_data())
