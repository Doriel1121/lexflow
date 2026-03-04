"""
Migration script to fix legacy users without a role assigned.
Sets all users with NULL role to LAWYER (default).
Run this once against your database to migrate existing users.
"""
import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.db.session import engine, AsyncSessionLocal
from app.db.models.user import User, UserRole


async def fix_legacy_users():
    """Assign LAWYER role to all users with NULL role."""
    async with AsyncSessionLocal() as session:
        # Count users with NULL roles
        result = await session.execute(select(User).filter(User.role.is_(None)))
        null_role_users = result.scalars().all()
        
        if not null_role_users:
            print("✓ No users with NULL roles found. Database is already migrated.")
            return
        
        print(f"Found {len(null_role_users)} users with NULL roles:")
        for user in null_role_users:
            print(f"  - {user.email} (ID: {user.id})")
        
        # Update all NULL roles to LAWYER
        stmt = update(User).where(User.role.is_(None)).values(role=UserRole.LAWYER)
        result = await session.execute(stmt)
        await session.commit()
        
        print(f"\n✓ Successfully updated {result.rowcount} users to role='lawyer'")


async def check_role_coverage():
    """Report on role distribution."""
    async with AsyncSessionLocal() as session:
        for role in UserRole:
            result = await session.execute(select(User).filter(User.role == role))
            count = len(result.scalars().all())
            print(f"  {role.value:12s}: {count:3d} users")
        
        # Also check for NULL
        result = await session.execute(select(User).filter(User.role.is_(None)))
        null_count = len(result.scalars().all())
        if null_count > 0:
            print(f"  {'<NULL>':12s}: {null_count:3d} users ❌ NEEDS FIX")
        else:
            print(f"  {'<NULL>':12s}:   0 users ✓")


async def main():
    print("=" * 60)
    print("User Role Migration Tool - LexFlow Backend")
    print("=" * 60)
    
    print("\n📊 Current role distribution:")
    await check_role_coverage()
    
    print("\n🔄 Fixing legacy users...")
    await fix_legacy_users()
    
    print("\n📊 Final role distribution:")
    await check_role_coverage()
    
    print("\n✅ Migration complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
