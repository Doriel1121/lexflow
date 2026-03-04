import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def upgrade_enum():
    from app.core.config import settings
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        try:
            # Add ORG_ADMIN in uppercase to match existing enum values
            await conn.execute(text("ALTER TYPE userrole ADD VALUE 'ORG_ADMIN' BEFORE 'ADMIN'"))
            print('✅ Successfully added ORG_ADMIN to userrole enum')
        except Exception as e:
            if 'already exists' in str(e):
                print('⚠️  ORG_ADMIN already exists in enum')
            else:
                print(f'❌ Error: {e}')
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(upgrade_enum())
