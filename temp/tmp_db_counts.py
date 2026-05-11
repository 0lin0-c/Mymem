import asyncio
import json
from sqlalchemy import text
from core.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        users = await session.execute(text('select count(*) as c from users'))
        resources = await session.execute(text('select count(*) as c from resources'))
        categories = await session.execute(text('select count(*) as c from categories'))
        print(json.dumps({
            'users': users.scalar_one(),
            'resources': resources.scalar_one(),
            'categories': categories.scalar_one(),
        }, ensure_ascii=False))

asyncio.run(main())
