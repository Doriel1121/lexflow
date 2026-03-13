# File Version: 2026-03-12T22:30:00
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func

from app.db.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate

class CRUDNotification:
    async def get(self, db: AsyncSession, id: int) -> Optional[Notification]:
        result = await db.execute(select(Notification).filter(Notification.id == id))
        return result.scalars().first()

    async def create_notification(self, db: AsyncSession, obj_in: NotificationCreate) -> Notification:
        db_obj = Notification(
            user_id=obj_in.user_id,
            organization_id=obj_in.organization_id,
            type=obj_in.type,
            title=obj_in.title,
            message=obj_in.message,
            link=obj_in.link,
            source_type=obj_in.source_type,
            source_id=obj_in.source_id,
            read=False
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    # Alias for compatibility
    async def create(self, *args, **kwargs):
        return await self.create_notification(*args, **kwargs)

    async def get_multi_by_user(
        self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Notification]:
        result = await db.execute(
            select(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unread_count_by_user(
        self, db: AsyncSession, *, user_id: int
    ) -> int:
        result = await db.execute(
            select(func.count(Notification.id))
            .filter(Notification.user_id == user_id, Notification.read == False)
        )
        return result.scalar_one()

    async def mark_as_read(
        self, db: AsyncSession, *, db_obj: Notification
    ) -> Notification:
        db_obj.read = True
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def mark_all_as_read(
        self, db: AsyncSession, *, user_id: int
    ) -> int:
        result = await db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read == False)
            .values(read=True)
            .returning(Notification.id)
        )
        await db.commit()
        updated_rows = result.scalars().all()
        return len(updated_rows)

notification_crud = CRUDNotification()
notification = notification_crud # Compatibility
