import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check_enum():
    from app.core.config import settings
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        try:
            result = await conn.execute(text("SELECT enum_range(NULL::userrole)"))
            enum_values = result.scalar()
            print(f'Current enum values: {enum_values}')
            
            # Also try to get from information_schema
            result2 = await conn.execute(text("""
                SELECT enumlabel FROM pg_enum 
                WHERE enumtypid = 'userrole'::regtype
                ORDER BY enumsortorder
            """))
            labels = result2.fetchall()
            print(f'Enum labels: {[row[0] for row in labels]}')
        except Exception as e:
            print(f'Error: {e}')
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check_enum())
