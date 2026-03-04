import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER', 'admin'), 
            password=os.getenv('DB_PASSWORD', 'change-me'), 
            database=os.getenv('DB_NAME', 'lexflow_db'), 
            host=os.getenv('DB_HOST', '127.0.0.1'), 
            port=int(os.getenv('DB_PORT', '5432'))
        )
        print('connected as', await conn.fetchval('select current_user'))
        await conn.close()
    except Exception as e:
        print('error:', type(e).__name__, e)

if __name__ == '__main__':
    asyncio.run(main())
