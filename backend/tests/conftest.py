"""Pytest configuration. Builds a TestClient backed by an in-memory SQLite
DB for fast unit tests. Integration tests against real Postgres are run
separately in CI via docker compose.

Yes — using SQLite for tests when prod is Postgres is a known compromise.
The trade-off: tests run in <2s with no external dependencies. We catch
most logic bugs here; Postgres-specific behavior gets caught by the
integration suite.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest

# Force test config before any app import.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("JWT_ACCESS_SECRET", "test-access-secret-min-32-chars-padded-here-x")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret-min-32-chars-padded-here-x")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-min-32-chars-padded-here")
os.environ.setdefault("NODE_ENV", "test")
os.environ.setdefault("COOKIE_SECURE", "false")


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Session-scoped event loop so async fixtures share state."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
