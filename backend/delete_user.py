import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def run():
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM users WHERE email ILIKE '%dorielaboya@gmail.com%'"))
        await db.commit()
        print("User dorielaboya@gmail.com (case insensitive) has been deleted successfully.")

asyncio.run(run())
