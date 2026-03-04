from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.base import Base
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False
)



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    import logging
    # Force FileHandler configuration for db debugging
    logger = logging.getLogger("db_session_debugger")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler('debug_db.log')
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
    
    logger.info("Creating new AsyncSession...")
    try:
        async with AsyncSessionLocal() as session:
            logger.info("Session created.")
            yield session
            logger.info("Session closed.")
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise
