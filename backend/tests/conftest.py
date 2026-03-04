import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings

# Override the database URL for testing
TEST_DATABASE_URL = settings.DATABASE_URL.replace("lexflow_db", "lexflow_test_db")

# Setup async engine for tests
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession)

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=False)
async def setup_test_db():
    """
    Fixture to set up and tear down the test database.
    Creates tables before tests, drops them after tests.
    """
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception as e:
        print(f"Skipping DB setup due to error: {e}")
        yield

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture that provides a clean, independent database session for each test function.
    """
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback() # Rollback changes after each test

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

