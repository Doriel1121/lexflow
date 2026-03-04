import asyncio
import sys
import os

# Add backend dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.organization import Organization

async def fix():
    async with AsyncSessionLocal() as db:
        users = await db.execute(select(User).where(User.organization_id == None))
        orphaned_users = users.scalars().all()
        
        if not orphaned_users:
            print("No orphaned users found.")
            return
            
        # Get the latest organization
        orgs = await db.execute(select(Organization).order_by(Organization.id.desc()).limit(1))
        latest_org = orgs.scalars().first()
        
        if not latest_org:
            print("No organizations found to link to.")
            return
            
        for u in orphaned_users:
            print(f"Fixing orphaned user: {u.email} -> Linking to Org ID: {latest_org.id}")
            u.organization_id = latest_org.id
            
        await db.commit()
        print("Success! All orphaned users fixed.")

asyncio.run(fix())
