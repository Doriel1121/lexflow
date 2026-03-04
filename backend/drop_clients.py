import asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.db.base import Base

engine = create_async_engine(settings.DATABASE_URL)

async def create():
    async with engine.begin() as conn:
        from app.db.models.audit_log import AuditLog
        await conn.run_sync(Base.metadata.create_all, tables=[AuditLog.__table__])
        print("Created audit_logs table")

asyncio.run(create())
