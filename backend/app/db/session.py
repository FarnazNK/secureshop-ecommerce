"""Async SQLAlchemy session management.

Uses asyncpg under the hood. The engine is created once at module load and
reused for the lifetime of the process. `get_db` is a FastAPI dependency
that yields a session per request and rolls back on exception.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()


# Convert postgres:// URL to postgresql+asyncpg:// for SQLAlchemy async engine.
# Pydantic gives us a normalized URL; we just adjust the scheme.
def _to_async_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


_DB_URL = _to_async_url(str(_settings.DATABASE_URL))


engine = create_async_engine(
    _DB_URL,
    # Echo SQL only in debug mode — too chatty otherwise.
    echo=_settings.LOG_LEVEL == "DEBUG",
    # Pool tuning: defaults are fine for portfolio scale. For prod, tune
    # based on observed concurrent requests vs DB capacity.
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,  # recycle connections every 30 min
)


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # let attributes stay accessible after commit
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session, rolls back on exception, closes always.

    Usage:
        @router.get(...)
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # No explicit commit — handlers commit when they're ready. This
        # avoids accidentally persisting partial state from a failed request.
