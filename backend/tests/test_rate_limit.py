"""Rate limiter backends: in-process memory and the shared database counter."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.rate_limit import DatabaseRateLimiter, MemoryRateLimiter, prune_buckets
from app.models.stripe_event import RateLimitBucket


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


async def test_memory_limiter_blocks_then_recovers() -> None:
    clock = Clock()
    limiter = MemoryRateLimiter(clock=clock)
    assert all([(await limiter.hit("ip", 3, 60)).allowed for _ in range(3)])
    blocked = await limiter.hit("ip", 3, 60)
    assert not blocked.allowed and 1 <= blocked.retry_after <= 60
    assert (await limiter.hit("other-ip", 3, 60)).allowed  # keys are independent
    clock.now += 61
    assert (await limiter.hit("ip", 3, 60)).allowed


async def test_two_instances_share_one_database_count(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    clock = Clock(1_000_040.0)
    # Two "servers" (e.g. two serverless instances) using the same database.
    first = DatabaseRateLimiter(sessions, clock=clock)
    second = DatabaseRateLimiter(sessions, clock=clock)

    results = [await (first if i % 2 else second).hit("ip", 5, 60) for i in range(7)]

    assert [r.allowed for r in results] == [True] * 5 + [False] * 2
    assert results[-1].retry_after == 40  # window 1,000,020..1,000,080 ends in 40s


async def test_database_count_resets_in_the_next_window(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    clock = Clock(1_000_000.0)
    limiter = DatabaseRateLimiter(sessions, clock=clock)
    for _ in range(2):
        await limiter.hit("ip", 2, 60)
    assert not (await limiter.hit("ip", 2, 60)).allowed
    clock.now += 60
    assert (await limiter.hit("ip", 2, 60)).allowed


async def test_raw_ip_is_not_stored(sessions: async_sessionmaker[AsyncSession]) -> None:
    await DatabaseRateLimiter(sessions).hit("api:203.0.113.9", 5, 60)
    async with sessions() as db:
        keys = (await db.scalars(select(RateLimitBucket.key))).all()
    assert len(keys) == 1 and "203.0.113.9" not in keys[0]


async def test_database_errors_fail_open() -> None:
    def broken_sessions():
        raise ConnectionError("database unreachable")

    limiter = DatabaseRateLimiter(broken_sessions)  # type: ignore[arg-type]
    assert (await limiter.hit("ip", 1, 60)).allowed
    assert (await limiter.hit("ip", 1, 60)).allowed


async def test_prune_removes_only_old_windows(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as db:
        db.add_all(
            [
                RateLimitBucket(key="old", window_start=1, count=3),
                RateLimitBucket(key="new", window_start=2_000_000_000, count=1),
            ]
        )
        await db.commit()
    assert await prune_buckets(sessions) == 1
    async with sessions() as db:
        assert (await db.scalars(select(RateLimitBucket.key))).all() == ["new"]


def test_middleware_returns_429_with_retry_after(client: TestClient) -> None:
    client.app.state.rate_limiter = MemoryRateLimiter()  # type: ignore[attr-defined]
    settings = get_settings()
    for _ in range(settings.AUTH_RATE_LIMIT_MAX_REQUESTS):
        client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x"})
    blocked = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # Stripe webhooks are never rate limited.
    assert client.post("/api/v1/payments/webhook", content=b"{}").status_code != 429


# ------------------------------------------------------------- PostgreSQL (CI)
@pytest.fixture
async def pg_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(str(get_settings().DATABASE_URL), pool_size=20, max_overflow=0)
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as connection:
                ready = await connection.run_sync(
                    lambda sync: sync.dialect.has_table(sync, "rate_limit_bucket")
                )
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL with migrations applied is not available (runs in CI)")
    if not ready:
        await engine.dispose()
        pytest.skip("run `alembic upgrade head` first")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_concurrent_requests_respect_the_shared_limit_on_postgres(
    pg_sessions: async_sessionmaker[AsyncSession],
) -> None:
    limiter = DatabaseRateLimiter(pg_sessions, timeout_seconds=10)
    key = f"burst-{uuid.uuid4()}"
    results = await asyncio.gather(*(limiter.hit(key, 10, 3600) for _ in range(40)))
    assert sum(r.allowed for r in results) == 10
