import asyncio
from core.database import AsyncSessionLocal
from sqlalchemy import text

async def t():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("SELECT 1"))
        print("DB OK:", r.scalar())

asyncio.run(t())
