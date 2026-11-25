"""Stripe Checkout flow: order creation, signed webhooks, retries and sync.

Runs against an in-memory SQLite database. Stripe's network calls are replaced
with fakes, but webhook signatures are generated and verified for real with
the Stripe SDK, so the security check is exercised end to end.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import Any

import pytest
import stripe
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.api.v1.orders import (
    create_order,
    create_order_checkout_session,
    sync_order_payment,
)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import CreateOrderRequest
from app.services import payments

WEBHOOK_SECRET = "whsec_test_secret_for_unit_tests"


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def fresh_breaker() -> Iterator[None]:
    """The Stripe circuit breaker is per process; isolate it between tests."""
    payments._breaker = None
    yield
    payments._breaker = None


@pytest.fixture
def stripe_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_unit")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("STRIPE_CURRENCY", "usd")
    monkeypatch.setenv("FRONTEND_URL", "https://shop.example")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def no_stripe_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeStripe:
    """Records Checkout Session calls and serves sessions from memory."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.sessions: dict[str, dict[str, Any]] = {}
        self.fail_create = False

    def create(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail_create:
            raise stripe.APIConnectionError("network down")
        self.created.append(kwargs)
        session_id = f"cs_test_{len(self.created)}"
        amount = sum(
            li["quantity"] * li["price_data"]["unit_amount"] for li in kwargs["line_items"]
        )
        session = {
            "id": session_id,
            "url": f"https://checkout.stripe.test/{session_id}",
            "status": "open",
            "payment_status": "unpaid",
            "client_reference_id": kwargs["client_reference_id"],
            "amount_total": amount,
            "currency": kwargs["line_items"][0]["price_data"]["currency"],
            "payment_intent": None,
        }
        self.sessions[session_id] = session
        return session

    def retrieve(self, session_id: str) -> dict[str, Any]:
        return self.sessions[session_id]

    def pay(self, session_id: str) -> dict[str, Any]:
        self.sessions[session_id].update(
            status="complete", payment_status="paid", payment_intent="pi_test_123"
        )
        return self.sessions[session_id]

    def expire(self, session_id: str) -> dict[str, Any]:
        self.sessions[session_id].update(status="expired")
        return self.sessions[session_id]


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(stripe.checkout.Session, "create", fake.create)
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", fake.retrieve)
    return fake


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def seed_cart(db: AsyncSession) -> tuple[User, Product]:
    """A shopper with 2 x $12.50 in the cart; product stock 10."""
    user = User(
        email="shopper@example.com",
        password_hash="unused",
        first_name="Pay",
        last_name="Tester",
    )
    product = Product(
        name="Field notebook",
        slug="field-notebook",
        description="Synthetic test product",
        price=Decimal("12.50"),
        stock_quantity=10,
        images=[],
    )
    db.add_all([user, product])
    await db.flush()
    cart = Cart(user_id=user.id)
    db.add(cart)
    await db.flush()
    db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=2, unit_price=product.price))
    await db.commit()
    return user, product


async def place_order(sessions: async_sessionmaker[AsyncSession]) -> tuple[Any, User, Product]:
    async with sessions() as db:
        user, product = await seed_cart(db)
        response = await create_order(
            CreateOrderRequest(notes=None), user=user, db=db, idempotency_key=None
        )
    return response, user, product


async def reload(sessions: async_sessionmaker[AsyncSession], order_id: str) -> Order:
    async with sessions() as db:
        order = await db.scalar(
            select(Order).where(Order.id == uuid.UUID(order_id)).options(selectinload(Order.items))
        )
        assert order is not None
        return order


async def stock(sessions: async_sessionmaker[AsyncSession], product: Product | Any) -> int:
    product_id = product if isinstance(product, uuid.UUID) else product.id
    async with sessions() as db:
        fresh = await db.get(Product, product_id)
        assert fresh is not None
        return fresh.stock_quantity


def signed(event: dict[str, Any], secret: str = WEBHOOK_SECRET) -> tuple[bytes, str]:
    payload = json.dumps(event).encode()
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return payload, f"t={timestamp},v1={signature}"


def event(event_type: str, session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"evt_{event_type}",
        "object": "event",
        "type": event_type,
        "data": {"object": session},
    }


@pytest.fixture
def client(sessions: async_sessionmaker[AsyncSession], stripe_env: None) -> Iterator[TestClient]:
    from app.main import create_app

    app = create_app()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------- tests
async def test_order_creates_checkout_session_and_reserves_stock(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, product = await place_order(sessions)

    assert response.checkout_url == "https://checkout.stripe.test/cs_test_1"
    assert response.order.status == OrderStatus.PENDING
    call = fake_stripe.created[0]
    assert call["mode"] == "payment"
    assert call["client_reference_id"] == response.order.id
    assert call["line_items"][0]["price_data"]["unit_amount"] == 1250
    assert call["line_items"][0]["quantity"] == 2
    assert (
        call["success_url"] == f"https://shop.example/orders/{response.order.id}?checkout=success"
    )
    assert call["idempotency_key"] == f"checkout-{response.order.id}-0"
    assert call["customer_email"] == "shopper@example.com"
    order = await reload(sessions, response.order.id)
    assert order.stripe_checkout_session_id == "cs_test_1"
    assert await stock(sessions, product) == 8


async def test_stripe_failure_saves_nothing(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    fake_stripe.fail_create = True
    async with sessions() as db:
        user, product = await seed_cart(db)
        product_id = product.id
        with pytest.raises(HTTPException) as exc:
            await create_order(
                CreateOrderRequest(notes=None), user=user, db=db, idempotency_key=None
            )
        # Network trouble = Stripe unavailable: 503 + Retry-After, cart kept.
        assert exc.value.status_code == 503
        assert exc.value.headers["Retry-After"]
        await db.rollback()  # what get_db does on an exception
    async with sessions() as db:
        assert (await db.scalars(select(Order))).all() == []
        assert len((await db.scalars(select(CartItem))).all()) == 1
    assert await stock(sessions, product_id) == 10


async def test_demo_mode_without_stripe(
    no_stripe_env: None, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, _product = await place_order(sessions)
    assert response.checkout_url is None
    assert response.order.status == OrderStatus.PENDING


async def test_signed_webhook_marks_order_paid_once(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, _product = await place_order(sessions)
    paid = fake_stripe.pay("cs_test_1")

    payload, signature = signed(event("checkout.session.completed", paid))
    result = client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )
    assert result.status_code == 200
    assert result.json() == {"status": "paid"}
    order = await reload(sessions, response.order.id)
    assert order.status == OrderStatus.PAID
    assert order.paid_at is not None
    assert order.stripe_payment_intent_id == "pi_test_123"

    # Stripe retries webhooks: a replay must change nothing.
    replay = client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )
    assert replay.json() == {"status": "already_paid"}


async def test_webhook_rejects_bad_or_missing_signature(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, _product = await place_order(sessions)
    paid = fake_stripe.pay("cs_test_1")
    payload, signature = signed(event("checkout.session.completed", paid), secret="whsec_wrong")

    forged = client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )
    missing = client.post("/api/v1/payments/webhook", content=payload)

    assert forged.status_code == 400
    assert missing.status_code == 400
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PENDING


async def test_amount_mismatch_does_not_mark_paid(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, _product = await place_order(sessions)
    tampered = dict(fake_stripe.pay("cs_test_1"), amount_total=100)
    payload, signature = signed(event("checkout.session.completed", tampered))

    result = client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )
    assert result.json() == {"status": "amount_mismatch"}
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PENDING


async def test_expired_checkout_cancels_order_and_restocks(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, product = await place_order(sessions)
    assert await stock(sessions, product) == 8
    expired = fake_stripe.expire("cs_test_1")
    payload, signature = signed(event("checkout.session.expired", expired))

    result = client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )
    assert result.json() == {"status": "cancelled"}
    assert (await reload(sessions, response.order.id)).status == OrderStatus.CANCELLED
    assert await stock(sessions, product) == 10


async def test_unrelated_session_cannot_cancel_order(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, product = await place_order(sessions)
    other = dict(fake_stripe.sessions["cs_test_1"], id="cs_test_old", status="expired")
    payload, signature = signed(event("checkout.session.expired", other))

    result = client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )
    assert result.json() == {"status": "ignored_stale_session"}
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PENDING
    assert await stock(sessions, product) == 8


async def test_sync_payment_marks_paid_before_webhook_arrives(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, user, _product = await place_order(sessions)
    fake_stripe.pay("cs_test_1")
    async with sessions() as db:
        synced = await sync_order_payment(response.order.id, user=user, db=db)
    assert synced.status == OrderStatus.PAID
    assert synced.paid_at is not None


async def test_pay_now_reuses_open_session_and_refuses_paid_order(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, user, _product = await place_order(sessions)
    async with sessions() as db:
        again = await create_order_checkout_session(response.order.id, user=user, db=db)
    assert again.checkout_url == "https://checkout.stripe.test/cs_test_1"
    assert len(fake_stripe.created) == 1  # no second payment page

    fake_stripe.pay("cs_test_1")
    async with sessions() as db:
        with pytest.raises(HTTPException) as exc:
            await create_order_checkout_session(response.order.id, user=user, db=db)
    assert exc.value.status_code == 409
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PAID


async def test_other_users_cannot_pay_or_sync_your_order(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response, _user, _product = await place_order(sessions)
    async with sessions() as db:
        stranger = User(
            email="stranger@example.com", password_hash="x", first_name="S", last_name="T"
        )
        db.add(stranger)
        await db.commit()
        for endpoint in (create_order_checkout_session, sync_order_payment):
            with pytest.raises(HTTPException) as exc:
                await endpoint(response.order.id, user=stranger, db=db)
            assert exc.value.status_code == 404


def test_payment_config_exposes_mode_not_secrets(client: TestClient) -> None:
    body = client.get("/api/v1/payments/config").json()
    assert body == {"enabled": True, "test_mode": True, "currency": "usd"}
