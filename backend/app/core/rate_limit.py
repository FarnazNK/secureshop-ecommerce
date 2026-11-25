"""Request rate limiting with two interchangeable backends.

memory    Sliding window kept in this process. Exact, zero cost, but each
          server instance counts separately.
database  Fixed-window counters in the existing Postgres (`rate_limit_bucket`),
          so every instance shares one count. One atomic upsert per request;
          no extra service needed.

Both answer the same question: may this key make another request now, and if
not, how many seconds until it may? The database backend fails open: if the
database is slow or down, requests are allowed (and counted in a metric)
rather than locking every user out because of the limiter.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from prometheus_client import Counter
from sqlalchemy import case, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.stripe_event import RateLimitBucket

log = get_logger(__name__)

RATE_LIMITED = Counter("secureshop_rate_limited_total", "Requests rejected (429)", ["bucket"])
RATE_LIMIT_ERRORS = Counter(
    "secureshop_rate_limit_backend_errors_total",
    "Limiter backend failures (request allowed: fail-open)",
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int = 0


class MemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    async def hit(self, key: str, limit: int, window_seconds: int) -> Decision:
        now = self._clock()
        events = self._windows[key]
        while events and now - events[0] >= window_seconds:
            events.popleft()
        if len(events) >= limit:
            return Decision(False, max(1, int(window_seconds - (now - events[0]))))
        events.append(now)
        return Decision(True)

    def reset(self) -> None:
        self._windows.clear()


def _insert_for(dialect: str):
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - only Postgres (prod) and SQLite (tests) are used
        raise RuntimeError(f"database rate limiting is not supported on {dialect}")
    return insert


class DatabaseRateLimiter:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], float] = time.time,
        timeout_seconds: float = 1.0,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._timeout = timeout_seconds

    @staticmethod
    def _storage_key(key: str) -> str:
        # Fixed length, and raw IPs aren't stored in the table.
        return hashlib.sha256(key.encode()).hexdigest()

    async def _count(self, key: str, window_start: int) -> int:
        async with self._sessions() as db:
            insert = _insert_for(db.bind.dialect.name)
            stmt = insert(RateLimitBucket).values(key=key, window_start=window_start, count=1)
            same_window = RateLimitBucket.window_start == stmt.excluded.window_start
            stmt = stmt.on_conflict_do_update(
                index_elements=[RateLimitBucket.key],
                set_={
                    "count": case((same_window, RateLimitBucket.count + 1), else_=1),
                    "window_start": stmt.excluded.window_start,
                },
            ).returning(RateLimitBucket.count)
            count = (await db.execute(stmt)).scalar_one()
            await db.commit()
            return count

    async def hit(self, key: str, limit: int, window_seconds: int) -> Decision:
        now = self._clock()
        window_start = int(now // window_seconds * window_seconds)
        try:
            count = await asyncio.wait_for(
                self._count(self._storage_key(key), window_start), self._timeout
            )
        except Exception as exc:
            RATE_LIMIT_ERRORS.inc()
            log.warning("rate_limit.backend_error", error=type(exc).__name__)
            return Decision(True)
        if count > limit:
            return Decision(False, max(1, int(window_start + window_seconds - now)))
        return Decision(True)


async def prune_buckets(
    sessions: async_sessionmaker[AsyncSession], *, older_than_seconds: int = 86_400
) -> int:
    """Delete counters whose window ended long ago (run by the hourly job)."""
    cutoff = int(time.time()) - older_than_seconds
    async with sessions() as db:
        result = await db.execute(
            delete(RateLimitBucket).where(RateLimitBucket.window_start < cutoff)
        )
        await db.commit()
        return result.rowcount or 0


def build_rate_limiter(backend: str):
    if backend == "database":
        from app.db.session import async_session_maker

        return DatabaseRateLimiter(async_session_maker)
    return MemoryRateLimiter()
