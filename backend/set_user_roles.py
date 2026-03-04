import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models.user import User, UserRole
from app.core.config import settings

async def update_user_roles():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Update doriel494@gmail.com to ADMIN
            result = await session.execute(
                select(User).filter(User.email == 'doriel494@gmail.com')
            )
            user1 = result.scalar_one_or_none()
            
            if user1:
                user1.role = UserRole.ADMIN
                print(f'✅ Updated {user1.email} to ADMIN')
            else:
                print(f'❌ User with email doriel494@gmail.com not found')
            
            # Update testdoriel@gmail.com to ORG_ADMIN
            result = await session.execute(
                select(User).filter(User.email == 'testdoriel@gmail.com')
            )
            user2 = result.scalar_one_or_none()
            
            if user2:
                user2.role = UserRole.ORG_ADMIN
                print(f'✅ Updated {user2.email} to ORG_ADMIN')
            else:
                print(f'❌ User with email testdoriel@gmail.com not found')
            
            await session.commit()
            
            # Verify changes
            print('\n📊 Final verification:')
            result = await session.execute(
                select(User).filter(User.email.in_(['doriel494@gmail.com', 'testdoriel@gmail.com']))
            )
            users = result.scalars().all()
            for user in users:
                print(f'  • {user.email}: {user.role.value}')
            
        except Exception as e:
            print(f'❌ Error: {e}')
            await session.rollback()
        finally:
            await engine.dispose()

if __name__ == '__main__':
    asyncio.run(update_user_roles())
