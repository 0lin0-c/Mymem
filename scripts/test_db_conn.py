import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(
        "postgresql://postgres:Xzc000813!@192.168.31.95:46195/postgres"
    )
    v = await conn.fetchval("SELECT 1")
    print(f"DB connection OK: {v}")
    await conn.close()

asyncio.run(test())
