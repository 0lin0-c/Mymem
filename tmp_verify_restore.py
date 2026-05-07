import asyncio
import json
from sqlalchemy import text
from core.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        user_rows = await session.execute(text("select id, username, created_at from users order by created_at asc"))
        counts = {}
        for table in ['users', 'resources', 'categories', 'resource_categories']:
            result = await session.execute(text(f'select count(*) as c from {table}'))
            counts[table] = result.scalar_one()
        print(json.dumps({
            'counts': counts,
            'users': [dict(r._mapping) for r in user_rows.fetchall()],
        }, ensure_ascii=False, indent=2, default=str))

asyncio.run(main())
