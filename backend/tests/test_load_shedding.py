"""Overload behaviour: shed with 503 instead of 500; cacheable catalogue reads."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


def test_pool_exhaustion_returns_retryable_503(client: TestClient) -> None:
    async def no_connection() -> AsyncIterator[AsyncSession]:
        raise SQLAlchemyTimeoutError("QueuePool limit reached")
        yield  # pragma: no cover

    client.app.dependency_overrides[get_db] = no_connection  # type: ignore[attr-defined]
    res = client.get("/api/v1/products")
    assert res.status_code == 503
    assert res.headers["Retry-After"] == "2"


def test_catalogue_reads_are_cdn_cacheable(client: TestClient) -> None:
    res = client.get("/api/v1/products")
    assert res.status_code == 200
    assert "s-maxage=30" in res.headers["Cache-Control"]
    assert "public" in res.headers["Cache-Control"]
