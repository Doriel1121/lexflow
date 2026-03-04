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
            print("User not found in DB!")
            return
            
        print("User:", user.email, "| Is Active:", user.is_active)
        print(f"Hashed Password in DB: {user.hashed_password}")
        
        # Test password
        test_pwd = "123123123" # The user said they typed 123123123
        print(f"Testing '{test_pwd}': {verify_password(test_pwd, user.hashed_password)}")
        
        # Forcefully rewrite it just in case
        print("Forcefully rewriting password to 123123123...")
        user.hashed_password = get_password_hash(test_pwd)
        await db.commit()
        print("Done.")

asyncio.run(check())
