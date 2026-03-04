import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.core.security import verify_password, get_password_hash

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == 'dorielaboya@gmail.com'))
        user = res.scalars().first()
        if not user:
            print("User not found!")
            return
            
        print("User:", user.email, "Is Active:", user.is_active)
        
        # Test password
        test_pwd = "password123" # The user said they typed 123123123
        print(f"Testing '123123123': {verify_password('123123123', user.hashed_password)}")
        
        # Overwrite password to be sure
        user.hashed_password = get_password_hash("123123123")
        await db.commit()
        print("Password forcefully reset to 123123123")

asyncio.run(check())
