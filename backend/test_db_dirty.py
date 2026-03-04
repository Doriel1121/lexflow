import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        print("--- Testing raw SQL ILIKE query ---")
        res1 = await db.execute(text("SELECT id, email, full_name, is_active FROM users WHERE email ILIKE '%dorielaboya@gmail.com%'"))
        print(res1.fetchall())
        
        print("\n--- Testing users table total count ---")
        res2 = await db.execute(text("SELECT count(*) FROM users"))
        print(res2.scalar())

asyncio.run(check())
