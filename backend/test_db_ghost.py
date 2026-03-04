import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        print("--- Finding ANY trace of Doriel ---")
        res1 = await db.execute(text("SELECT id, email FROM users WHERE email ILIKE '%doriel%'"))
        rows = res1.fetchall()
        for r in rows:
            print(f"ID: {r.id} | Email: '{r.email}'")

        print("--- DELETING ALL TRACES ---")
        await db.execute(text("DELETE FROM users WHERE email ILIKE '%dorielaboya%'"))
        await db.commit()
        print("Done. Fully wiped.")

asyncio.run(check())
