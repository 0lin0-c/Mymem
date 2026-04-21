import asyncio
from core.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("SELECT category_name, count(*) FROM categories GROUP BY category_name ORDER BY count(*) DESC"))
        print("Category distribution:")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

asyncio.run(check())
