import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT id, name FROM clients'))
        clients = [dict(row._mapping) for row in result]
        print('Clients:', clients)
        if not clients:
            print('No clients found! Creating test clients...')
            await db.execute(text("INSERT INTO clients (name, contact_email) VALUES ('Test Client 1', 'test1@example.com'), ('Test Client 2', 'test2@example.com')"))
            await db.commit()
            print('Created 2 test clients')

asyncio.run(check())
