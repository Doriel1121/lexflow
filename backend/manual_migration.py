import asyncio
from sqlalchemy import text
from app.db.session import engine

async def run():
    async with engine.begin() as conn:
        try:
            print("Adding category column to tags table...")
            await conn.execute(text("ALTER TABLE tags ADD COLUMN category VARCHAR;"))
            await conn.execute(text("CREATE INDEX ix_tags_category ON tags (category);"))
            print("Successfully explicitly altered tags table!")
        except Exception as e:
            print(f"Error: {e}")
            
if __name__ == "__main__":
    asyncio.run(run())
