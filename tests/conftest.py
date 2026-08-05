"""
Test fixtures.

Uses a dedicated, function-scoped engine with NullPool (no connection
pooling) rather than the app's shared engine -- pooled async connections
are bound to the event loop they were created on, and pytest-asyncio
gives each test its own loop by default. Reusing the app's pooled engine
across tests causes "attached to a different loop" errors. A fresh,
unpooled engine per test sidesteps the problem entirely.
"""
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base_all_models import Base
from app.db.session import get_db
from app.main import app

#_test_db_url = str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://", 1).rsplit("/", 1)[0] + "/trip_expense_test"

_test_db_url = (
    str(settings.DATABASE_URL)
    .replace("postgresql://", "postgresql+asyncpg://", 1)
    .rsplit("/", 1)[0]
    + "/trip_expense_test"
)

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(_test_db_url, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def valid_register_payload() -> dict:
    return {
        "email": "traveler@example.com",
        "password": "SecurePass123",
        "display_name": "Test Traveler",
    }