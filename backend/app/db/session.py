"""Async SQLAlchemy session management.

Uses asyncpg under the hood. The engine is created once at module load and
reused for the lifetime of the process. `get_db` is a FastAPI dependency
that yields a session per request and rolls back on exception.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()


# Convert PostgreSQL URLs to the asyncpg dialect and remove libpq-only query
# parameters (for example Neon may add channel_binding/sslmode).
def _to_async_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        converted = raw
    elif raw.startswith("postgresql://"):
        converted = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgres://"):
        converted = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        converted = raw

    parts = urlsplit(converted)
    safe_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"channel_binding", "sslmode"}
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(safe_query), parts.fragment)
    )


_DB_URL = _to_async_url(str(_settings.DATABASE_URL))


def _connect_args() -> dict:
    if not _DB_URL.startswith("postgresql+asyncpg://"):
        return {}
    # command_timeout is enforced by the asyncpg client, so it works through
    # Neon's pooler (which rejects server-side startup parameters).
    args: dict = {"command_timeout": _settings.DB_COMMAND_TIMEOUT_SECONDS}
    if _settings.DATABASE_SSL:
        args["ssl"] = True
    return args


engine = create_async_engine(
    _DB_URL,
    connect_args=_connect_args(),
    # Echo SQL only in debug mode — too chatty otherwise.
    echo=_settings.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,
    # Serverless: no pool (each invocation is short-lived; Neon's pooler does
    # the pooling). Long-running servers: a small pool per replica. Keep
    # replicas x (DB_POOL_SIZE + DB_MAX_OVERFLOW) under the database's
    # connection limit, and fail fast (503) instead of queueing forever.
    **(
        {"poolclass": NullPool}
        if _settings.DB_POOL_DISABLED
        else {
            "pool_size": _settings.DB_POOL_SIZE,
            "max_overflow": _settings.DB_MAX_OVERFLOW,
            "pool_timeout": _settings.DB_POOL_TIMEOUT_SECONDS,
            "pool_recycle": 1800,
        }
    ),
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
