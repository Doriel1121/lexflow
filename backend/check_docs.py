import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT id, filename, case_id, content FROM documents ORDER BY id DESC LIMIT 3'))
        for row in result:
            print(f'ID: {row[0]}, File: {row[1]}, Case: {row[2]}, Content: {row[3][:100] if row[3] else "None"}')

asyncio.run(check())
