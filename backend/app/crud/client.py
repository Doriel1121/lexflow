from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.client import Client as DBClient
from app.schemas.client import ClientCreate, ClientUpdate

class CRUDClient:
    async def get(self, db: AsyncSession, id: int) -> Optional[DBClient]:
        result = await db.execute(select(DBClient).where(DBClient.id == id))
        return result.scalars().first()

    async def get_multi_by_organization(
        self, db: AsyncSession, *, organization_id: int, skip: int = 0, limit: int = 100
    ) -> List[DBClient]:
        stmt = select(DBClient).where(DBClient.organization_id == organization_id).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: ClientCreate, organization_id: int) -> DBClient:
        db_obj = DBClient(
            **obj_in.model_dump(),
            organization_id=organization_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: DBClient, obj_in: ClientUpdate) -> DBClient:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: int) -> DBClient:
        obj = await self.get(db=db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

client_crud = CRUDClient()
