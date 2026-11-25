"""Production-hardening tests: circuit breaker, Stripe timeouts, atomic stock
and idempotent order creation.

SQLite tests run everywhere. The concurrency tests need real PostgreSQL row
locking: they run in CI (which provides PostgreSQL and applies migrations) and
are skipped locally when no database is reachable.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import Any

import pytest
import stripe
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.orders import create_order
from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from app.core.config import get_settings
from app.db.base import Base
from app.models.cart import Cart, CartItem
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.order import CreateOrderRequest
from app.services import payments


# ----------------------------------------------------------------- circuit breaker
class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_breaker(clock: FakeClock) -> CircuitBreaker:
    return CircuitBreaker(
        f"test-{uuid.uuid4().hex[:6]}",
        failure_threshold=3,
        window_seconds=60,
        reset_timeout_seconds=30,
        clock=clock,
    )


def test_breaker_opens_after_threshold_and_fails_fast() -> None:
    clock = FakeClock()
    breaker = make_breaker(clock)
    for _ in range(3):
        breaker.before_call()
        breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError) as exc:
        breaker.before_call()
    assert 1 <= exc.value.retry_after <= 30


def test_breaker_ignores_failures_outside_window() -> None:
    clock = FakeClock()
    breaker = make_breaker(clock)
    for _ in range(2):
        breaker.record_failure()
    clock.now += 61
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED


def test_breaker_half_open_allows_one_trial_then_closes_on_success() -> None:
    clock = FakeClock()
    breaker = make_breaker(clock)
    for _ in range(3):
        breaker.record_failure()
    clock.now += 31
    assert breaker.state == CircuitState.HALF_OPEN
    breaker.before_call()  # the trial
    with pytest.raises(CircuitOpenError):
        breaker.before_call()  # a second concurrent call is still rejected
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    breaker.before_call()


def test_breaker_reopens_if_trial_fails_and_abandoned_trial_is_released() -> None:
    clock = FakeClock()
    breaker = make_breaker(clock)
    for _ in range(3):
        breaker.record_failure()
    clock.now += 31
    breaker.before_call()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    clock.now += 31
    breaker.before_call()
    breaker.abandon_trial()  # e.g. the request was cancelled
    breaker.before_call()  # slot is free again


# ------------------------------------------------------- Stripe calls behind breaker
@pytest.fixture
def stripe_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_unit")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_unit")
    monkeypatch.setenv("STRIPE_BREAKER_FAILURE_THRESHOLD", "3")
    monkeypatch.setenv("FRONTEND_URL", "https://shop.example")
    get_settings.cache_clear()
    payments._breaker = None
    yield
    payments._breaker = None
    get_settings.cache_clear()


async def test_stripe_outage_trips_breaker_and_stops_calling_stripe(
    stripe_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def failing(*_args: Any, **_kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        raise stripe.APIConnectionError("timed out")

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", failing)
    settings = get_settings()
    for _ in range(3):
        with pytest.raises(payments.PaymentUnavailableError):
            await payments.retrieve_checkout_session(settings, "cs_x")
    assert calls == 3

    with pytest.raises(payments.PaymentUnavailableError) as exc:
        await payments.retrieve_checkout_session(settings, "cs_x")
    assert calls == 3  # failed fast: Stripe was not called again
    assert exc.value.retry_after >= 1


async def test_stripe_rejecting_a_request_does_not_trip_breaker(
    stripe_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid(*_args: Any, **_kwargs: Any) -> None:
        raise stripe.InvalidRequestError("No such session", param="id", http_status=404)

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", invalid)
    settings = get_settings()
    for _ in range(5):
        with pytest.raises(payments.PaymentError) as exc:
            await payments.retrieve_checkout_session(settings, "cs_missing")
        assert not isinstance(exc.value, payments.PaymentUnavailableError)
    assert payments.get_breaker(settings).state == CircuitState.CLOSED


async def test_stripe_client_uses_short_timeout_and_bounded_retries(
    stripe_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *_a, **_k: {"id": "cs"})
    await payments.retrieve_checkout_session(get_settings(), "cs")
    assert stripe.default_http_client._timeout == 10.0
    assert stripe.max_network_retries == 2


# ------------------------------------------------------------ stock + idempotency
@pytest.fixture
def no_stripe(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def sqlite_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def make_product(db: AsyncSession, stock: int) -> Product:
    tag = uuid.uuid4().hex[:8]
    product = Product(
        name=f"Last-unit lamp {tag}",
        slug=f"lamp-{tag}",
        description="Synthetic",
        price=Decimal("40.00"),
        stock_quantity=stock,
        images=[],
    )
    db.add(product)
    await db.commit()
    return product


async def make_shopper(db: AsyncSession, product_id: uuid.UUID, quantity: int = 1) -> User:
    tag = uuid.uuid4().hex[:8]
    user = User(email=f"buyer-{tag}@example.com", password_hash="x", first_name="B", last_name=tag)
    db.add(user)
    await db.flush()
    cart = Cart(user_id=user.id)
    db.add(cart)
    await db.flush()
    db.add(
        CartItem(
            cart_id=cart.id, product_id=product_id, quantity=quantity, unit_price=Decimal("40")
        )
    )
    await db.commit()
    return user


async def stock_of(sessions: async_sessionmaker[AsyncSession], product_id: uuid.UUID) -> int:
    async with sessions() as db:
        product = await db.get(Product, product_id)
        assert product is not None
        return product.stock_quantity


async def test_last_unit_goes_to_exactly_one_buyer(
    no_stripe: None, sqlite_sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with sqlite_sessions() as db:
        product = await make_product(db, stock=1)
        first = await make_shopper(db, product.id)
        second = await make_shopper(db, product.id)
    product_id = product.id

    async with sqlite_sessions() as db:
        await create_order(CreateOrderRequest(), user=first, db=db, idempotency_key=None)
    async with sqlite_sessions() as db:
        with pytest.raises(HTTPException) as exc:
            await create_order(CreateOrderRequest(), user=second, db=db, idempotency_key=None)
    assert exc.value.status_code == 409
    assert await stock_of(sqlite_sessions, product_id) == 0
    async with sqlite_sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Order)) == 1
        # The losing buyer's cart is untouched, so they can adjust and retry.
        assert await db.scalar(select(func.count()).select_from(CartItem)) == 1


async def test_same_idempotency_key_returns_the_first_order(
    no_stripe: None, sqlite_sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with sqlite_sessions() as db:
        product = await make_product(db, stock=5)
        user = await make_shopper(db, product.id, quantity=2)
    key = f"checkout-{uuid.uuid4()}"

    async with sqlite_sessions() as db:
        first = await create_order(CreateOrderRequest(), user=user, db=db, idempotency_key=key)
    async with sqlite_sessions() as db:
        retry = await create_order(CreateOrderRequest(), user=user, db=db, idempotency_key=key)

    assert retry.order.id == first.order.id
    assert await stock_of(sqlite_sessions, product.id) == 3  # reserved once, not twice
    async with sqlite_sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Order)) == 1


# ----------------------------------------------------- PostgreSQL concurrency (CI)
@pytest.fixture
async def pg_sessions(no_stripe: None) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = str(get_settings().DATABASE_URL)
    engine = create_async_engine(url, pool_size=25, max_overflow=0)
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as connection:
                tables = await connection.run_sync(
                    lambda sync: sync.dialect.has_table(sync, "rate_limit_bucket")
                )
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL with migrations applied is not available (runs in CI)")
    if not tables:
        await engine.dispose()
        pytest.skip("run `alembic upgrade head` first")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_concurrent_buyers_never_oversell_on_postgres(
    pg_sessions: async_sessionmaker[AsyncSession],
) -> None:
    stock, buyers = 5, 20
    async with pg_sessions() as db:
        product = await make_product(db, stock=stock)
        users = [await make_shopper(db, product.id) for _ in range(buyers)]

    async def buy(user: User) -> int:
        async with pg_sessions() as db:
            try:
                await create_order(CreateOrderRequest(), user=user, db=db, idempotency_key=None)
                return 201
            except HTTPException as exc:
                await db.rollback()
                return exc.status_code

    results = await asyncio.gather(*(buy(u) for u in users))
    assert results.count(201) == stock
    assert results.count(409) == buyers - stock
    assert await stock_of(pg_sessions, product.id) == 0


async def test_concurrent_retries_with_one_key_create_one_order_on_postgres(
    pg_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_sessions() as db:
        product = await make_product(db, stock=10)
        user = await make_shopper(db, product.id, quantity=1)
    key = f"double-click-{uuid.uuid4()}"

    async def submit() -> str:
        async with pg_sessions() as db:
            response = await create_order(
                CreateOrderRequest(), user=user, db=db, idempotency_key=key
            )
            return response.order.id

    order_ids = await asyncio.gather(*(submit() for _ in range(5)), return_exceptions=True)
    successful = {o for o in order_ids if isinstance(o, str)}
    assert len(successful) == 1, order_ids
    async with pg_sessions() as db:
        count = await db.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user.id)
        )
    assert count == 1
    assert await stock_of(pg_sessions, product.id) == 9
