import os
os.environ["B2_ENABLED"] = "false"
os.environ["R2_ENABLED"] = "false"
os.environ["STORAGE_BACKEND"] = "local"

import sys
import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings

# Override the database URL for testing
TEST_DATABASE_URL = settings.DATABASE_URL.replace("renew_legalos_db", "renew_legalos_test_db").replace("lexflow_db", "lexflow_test_db")
if "@db:" in TEST_DATABASE_URL:
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace("@db:", "@127.0.0.1:")

# Setup async engine for session-level database creation/teardown
session_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """
    Fixture to set up and tear down the test database.
    Creates tables before tests, drops them after tests.
    """
    try:
        async with session_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with session_engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE;"))
            await conn.execute(text("CREATE SCHEMA public;"))
    except Exception as e:
        print(f"Skipping DB setup due to error: {e}")
        yield
    finally:
        await session_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture that provides a clean, independent database session for each test function.
    Creates a new engine for the current test's event loop and disposes it afterwards.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Mock commit as flush to prevent object expiration and actual database commits
        session.commit = session.flush
        yield session
        await session.rollback() # Rollback changes after each test
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture for a FastAPI test client, overriding the get_db dependency.
    """
    from httpx import ASGITransport

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

