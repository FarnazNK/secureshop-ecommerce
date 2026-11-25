"""Shared fixtures and helpers for the payment tests (loaded via conftest).

In-memory SQLite database, faked Stripe network calls, and real webhook
signatures generated with the same scheme Stripe uses.
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
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.api.v1.orders import (
    create_order,
)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order
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
