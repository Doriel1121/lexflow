from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.db.models.user import User as DBUser, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash

class CRUDUser:
    async def get(self, db: AsyncSession, user_id: int) -> Optional[DBUser]:
        result = await db.execute(select(DBUser).filter(DBUser.id == user_id))
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[DBUser]:
        result = await db.execute(select(DBUser).filter(DBUser.email == email))
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DBUser]:
        result = await db.execute(select(DBUser).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, user_in: UserCreate, organization_id: Optional[int] = None) -> DBUser:
        hashed_password = get_password_hash(user_in.password)
        db_user = DBUser(
            email=user_in.email,
            hashed_password=hashed_password,
            full_name=user_in.full_name,
            is_active=True, # Default to active
            is_superuser=False, # Default to non-superuser
            social_id=user_in.social_id,
            provider=user_in.provider,
            role=user_in.role or UserRole.LAWYER, # Default role
            organization_id=organization_id
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user

    async def update(self, db: AsyncSession, user_id: int, user_in: UserUpdate) -> Optional[DBUser]:
        db_user = await self.get(db, user_id)
        if not db_user:
            return None
        
        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]
        
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        await db.commit()
        await db.refresh(db_user)
        return db_user

    async def delete(self, db: AsyncSession, user_id: int) -> Optional[DBUser]:
        db_user = await self.get(db, user_id)
        if not db_user:
            return None
        await db.delete(db_user)
        await db.commit()
        return db_user

user_crud = CRUDUser()
