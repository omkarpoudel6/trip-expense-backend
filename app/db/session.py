"""
Async database engine + session factory, and the FastAPI dependency
that hands a session to each request and guarantees cleanup.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# POstgres URL comes in as postgresql:// -- asyncpg needs postgresql+asyncpg://
_async_db_url = str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}

if "localhost" not in _async_db_url and "127.0.0.1" not in _async_db_url:
    connect_args = {"ssl": "require"}

engine = create_async_engine(
    _async_db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True, # avoids stale-connection errors after idle periods
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()