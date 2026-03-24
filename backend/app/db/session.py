from typing import AsyncGenerator
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

# ── Engine kwargs ─────────────────────────────────────────────────────────
# In production (Render / any managed Postgres) SSL is required.
# asyncpg reads ssl from the connect_args dict.
# In development (@db:5432 Docker network) SSL is not available — skip it.

_is_production = os.getenv("APP_ENV", "development").lower() == "production"

_connect_args: dict = {}
if _is_production:
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,           # set to True only when debugging queries locally
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dedicated engine for Celery tasks — NullPool prevents cross-loop connection sharing
celery_engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
    connect_args=_connect_args,
)

CeleryAsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
