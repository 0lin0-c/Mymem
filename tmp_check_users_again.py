import asyncio
import json
from sqlalchemy import text
from core.database import AsyncSessionLocal
from core.config import settings

async def main():
    async with AsyncSessionLocal() as session:
        users = await session.execute(text('select id, username from users order by created_at asc'))
        print(json.dumps({'database_url': settings.database_url, 'users': [dict(r._mapping) for r in users.fetchall()]}, ensure_ascii=False, indent=2))

asyncio.run(main())
