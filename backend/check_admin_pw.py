import asyncio
import os
import sys

# Add backend dir to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.core.security import get_password_hash

async def check_admin():
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "doriel494@gmail.com"))
        if not user:
            print("User not found: doriel494@gmail.com")
            return
            
        print("Force resetting password to 'adminpassword'")
        user.hashed_password = get_password_hash("adminpassword")
        await db.commit()
        print("Password successfully reset to 'adminpassword'")

asyncio.run(check_admin())
