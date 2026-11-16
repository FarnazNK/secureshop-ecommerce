"""Checkout idempotency, stock reservation and Stripe webhooks against real PostgreSQL.

These behaviors depend on Postgres row locks and unique constraints, so they run against the
database in DATABASE_URL (CI provides one with migrations applied). Concurrency is forced: a
fake Stripe call holds the first checkout's transaction open for a moment, so competing
requests reach the database while it is still in flight.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import itertools
import json
import os
import threading
import time
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from types import SimpleNamespace

import pytest
import stripe
from fastapi import HTTPException, Response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1 import orders as orders_api
from app.api.v1 import payments as payments_api
from app.core.config import get_settings
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderStatus
from app.models.payment import IdempotencyKey, StripeEvent
from app.models.product import Product
from app.models.user import User
from app.schemas.order import CreateOrderRequest

WEBHOOK_SECRET = "whsec_test_secret_for_signature_checks"
STRIPE_DELAY_SECONDS = 0.3


# ----------------------------------------------------------------------------- fixtures


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    url = make_url(os.environ["DATABASE_URL"])
    if not url.drivername.startswith("postgresql") or "test" not in (url.database or ""):
        pytest.skip("needs a disposable PostgreSQL test database in DATABASE_URL")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    'TRUNCATE stripe_event, idempotency_key, order_item, "order", cart_item, '
                    'cart, product_image, product, category, refresh_token, "user" CASCADE'
                )
            )
    except OSError as exc:
        await engine.dispose()
        if os.environ.get("CI"):
            raise
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    yield engine
    await engine.dispose()


@pytest.fixture
def sessions(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


class FakeStripe:
    """Stands in for the Stripe SDK. Like Stripe, it returns the same payment intent for a
    repeated idempotency key. Each call blocks its worker thread briefly (as a real network
    call would), which keeps the calling checkout's transaction open."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.intents: dict[str, SimpleNamespace] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def create(self, **kwargs):
        time.sleep(STRIPE_DELAY_SECONDS)
        with self._lock:
            self.calls.append(kwargs)
            key = kwargs["idempotency_key"]
            if key not in self.intents:
                number = next(self._ids)
                self.intents[key] = SimpleNamespace(
                    id=f"pi_test_{number}", client_secret=f"pi_test_{number}_secret"
                )
            return self.intents[key]

    def retrieve(self, intent_id):
        return next(i for i in self.intents.values() if i.id == intent_id)


@pytest.fixture
def fake_stripe(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(stripe.PaymentIntent, "create", fake.create)
    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", fake.retrieve)
    settings = get_settings().model_copy(
        update={"STRIPE_SECRET_KEY": "sk_test_fake", "STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET}
    )
    monkeypatch.setattr(orders_api, "get_settings", lambda: settings)
    monkeypatch.setattr(payments_api, "get_settings", lambda: settings)
    return fake


# ----------------------------------------------------------------------------- helpers


async def make_user(sessions, email: str) -> uuid.UUID:
    async with sessions() as db:
        user = User(email=email, password_hash="unused", first_name="Test", last_name="User")
        db.add(user)
        await db.commit()
        return user.id


async def make_product(sessions, *, stock: int, price: str = "25.00") -> uuid.UUID:
    async with sessions() as db:
        product = Product(
            name=f"Product {uuid.uuid4().hex[:6]}",
            slug=f"product-{uuid.uuid4().hex}",
            price=Decimal(price),
            stock_quantity=stock,
            images=[],
        )
        db.add(product)
        await db.commit()
        return product.id


async def fill_cart(sessions, user_id, product_id, quantity: int) -> None:
    async with sessions() as db:
        price = (await db.get(Product, product_id)).price
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.flush()
        db.add(
            CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity, unit_price=price)
        )
        await db.commit()


async def checkout(sessions, user_id, key: str | None, notes: str | None = None):
    """Call the endpoint function as FastAPI would. Returns (status, body or detail, headers)."""
    async with sessions() as db:
        user = await db.get(User, user_id)
        # FastAPI injects a Response with no status, so the route's 201 applies unless the
        # endpoint sets one (as a replay does).
        response = Response()
        response.status_code = None  # type: ignore[assignment]
        try:
            result = await orders_api.create_order(
                payload=CreateOrderRequest(notes=notes),
                response=response,
                user=user,
                db=db,
                idempotency_key=key,
            )
        except HTTPException as exc:
            return exc.status_code, exc.detail, {}
        return response.status_code or 201, result, dict(response.headers)


async def scalar(sessions, query):
    async with sessions() as db:
        return await db.scalar(query)


async def stock_of(sessions, product_id) -> int:
    return await scalar(sessions, select(Product.stock_quantity).where(Product.id == product_id))


async def order_count(sessions) -> int:
    return await scalar(sessions, select(func.count()).select_from(Order))


# ----------------------------------------------------------------------------- idempotency


async def test_retry_with_same_key_returns_the_original_order(sessions, fake_stripe):
    user = await make_user(sessions, "retry@example.com")
    product = await make_product(sessions, stock=5)
    await fill_cart(sessions, user, product, 2)

    first = await checkout(sessions, user, "checkout-key-0001")
    # The cart is now empty, so a second order could not be placed: only a replay succeeds.
    second = await checkout(sessions, user, "checkout-key-0001")

    assert first[0] == 201 and second[0] == 200
    assert second[2]["idempotent-replayed"] == "true"
    assert second[1].order.id == first[1].order.id
    assert second[1].payment_intent_client_secret == first[1].payment_intent_client_secret
    assert await order_count(sessions) == 1
    assert await stock_of(sessions, product) == 3
    assert len(fake_stripe.calls) == 1


async def test_concurrent_requests_with_same_key_create_one_order(sessions, fake_stripe):
    user = await make_user(sessions, "double-click@example.com")
    product = await make_product(sessions, stock=5)
    await fill_cart(sessions, user, product, 1)

    results = await asyncio.gather(
        *(checkout(sessions, user, "double-click-key") for _ in range(5))
    )

    assert sorted(status for status, _, _ in results) == [200, 200, 200, 200, 201]
    assert len({body.order.id for _, body, _ in results}) == 1
    assert await order_count(sessions) == 1
    assert await stock_of(sessions, product) == 4
    assert len(fake_stripe.calls) == 1


async def test_same_key_with_different_body_is_rejected(sessions, fake_stripe):
    user = await make_user(sessions, "mismatch@example.com")
    product = await make_product(sessions, stock=5)
    await fill_cart(sessions, user, product, 1)

    assert (await checkout(sessions, user, "reused-key-1234", notes="gift"))[0] == 201
    status_code, detail, _ = await checkout(sessions, user, "reused-key-1234", notes="other")

    assert status_code == 422
    assert "different request body" in detail
    assert await order_count(sessions) == 1


async def test_keys_are_scoped_per_user(sessions, fake_stripe):
    product = await make_product(sessions, stock=5)
    alice = await make_user(sessions, "alice@example.com")
    bob = await make_user(sessions, "bob@example.com")
    await fill_cart(sessions, alice, product, 1)
    await fill_cart(sessions, bob, product, 1)

    a = await checkout(sessions, alice, "shared-key-value")
    b = await checkout(sessions, bob, "shared-key-value")

    assert a[0] == b[0] == 201
    assert a[1].order.id != b[1].order.id


async def test_failed_checkout_releases_the_key_for_a_retry(sessions, fake_stripe):
    user = await make_user(sessions, "out-of-stock@example.com")
    product = await make_product(sessions, stock=1)
    await fill_cart(sessions, user, product, 2)

    assert (await checkout(sessions, user, "retry-after-409"))[0] == 409
    assert await scalar(sessions, select(func.count()).select_from(IdempotencyKey)) == 0

    async with sessions() as db:
        await db.execute(text("UPDATE product SET stock_quantity = 2"))
        await db.commit()
    assert (await checkout(sessions, user, "retry-after-409"))[0] == 201


async def test_stripe_gets_an_idempotency_key_derived_from_the_request(sessions, fake_stripe):
    user = await make_user(sessions, "stripe-key@example.com")
    product = await make_product(sessions, stock=5, price="19.99")
    await fill_cart(sessions, user, product, 3)

    await checkout(sessions, user, "stripe-key-0001")

    call = fake_stripe.calls[0]
    assert call["idempotency_key"] == f"checkout:{user}:stripe-key-0001"
    assert call["amount"] == 5997  # exact cents for 3 x 19.99


# ----------------------------------------------------------------------------- stock


async def test_last_unit_cannot_be_sold_twice(sessions, fake_stripe):
    product = await make_product(sessions, stock=1)
    buyers = [await make_user(sessions, f"buyer{i}@example.com") for i in range(4)]
    for buyer in buyers:
        await fill_cart(sessions, buyer, product, 1)

    results = await asyncio.gather(
        *(checkout(sessions, buyer, f"buyer-key-{i:04d}") for i, buyer in enumerate(buyers))
    )

    statuses = sorted(status for status, _, _ in results)
    assert statuses == [201, 409, 409, 409]
    assert await stock_of(sessions, product) == 0
    assert await order_count(sessions) == 1


async def test_checkout_of_several_products_is_all_or_nothing(sessions, fake_stripe):
    plenty = await make_product(sessions, stock=10)
    scarce = await make_product(sessions, stock=0)
    user = await make_user(sessions, "partial@example.com")
    async with sessions() as db:
        cart = Cart(user_id=user)
        db.add(cart)
        await db.flush()
        for product_id in (plenty, scarce):
            db.add(
                CartItem(
                    cart_id=cart.id, product_id=product_id, quantity=1, unit_price=Decimal("1")
                )
            )
        await db.commit()

    assert (await checkout(sessions, user, "partial-stock-key"))[0] == 409
    assert await stock_of(sessions, plenty) == 10  # the first reservation rolled back
    assert await order_count(sessions) == 0


# ----------------------------------------------------------------------------- webhooks


def signed(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def event(event_id: str, event_type: str, intent_id: str, amount: int) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {
                "object": {
                    "id": intent_id,
                    "object": "payment_intent",
                    "amount_received": amount,
                    "currency": "usd",
                }
            },
        }
    ).encode()


@pytest.fixture
async def client(sessions) -> AsyncIterator[AsyncClient]:
    from app.db.session import get_db
    from app.main import create_app

    app = create_app()

    async def test_db():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def pending_order(sessions, *, stock: int = 3, quantity: int = 2):
    """A real checkout: returns (order id, payment intent id, total in cents, product id)."""
    user = await make_user(sessions, f"payer-{uuid.uuid4().hex[:8]}@example.com")
    product = await make_product(sessions, stock=stock, price="10.00")
    await fill_cart(sessions, user, product, quantity)
    _, body, _ = await checkout(sessions, user, f"pay-{uuid.uuid4().hex}")
    order = await scalar(sessions, select(Order).where(Order.id == uuid.UUID(body.order.id)))
    return order.id, order.stripe_payment_intent_id, int(order.total * 100), product


async def post_event(client, payload: bytes, signature: str | None = None):
    return await client.post(
        "/api/v1/payments/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": signature or signed(payload)},
    )


async def status_of(sessions, order_id) -> OrderStatus:
    return await scalar(sessions, select(Order.status).where(Order.id == order_id))


async def test_payment_succeeded_marks_order_paid_once(sessions, fake_stripe, client):
    order_id, intent, cents, _ = await pending_order(sessions)
    payload = event("evt_paid_1", "payment_intent.succeeded", intent, cents)

    first = await post_event(client, payload)
    again = await post_event(client, payload)

    assert first.status_code == 200 and first.json() == {"status": "paid"}
    assert again.status_code == 200 and again.json() == {"status": "duplicate"}
    assert await status_of(sessions, order_id) == OrderStatus.PAID


async def test_wrong_amount_does_not_mark_order_paid(sessions, fake_stripe, client):
    order_id, intent, cents, _ = await pending_order(sessions)

    response = await post_event(
        client, event("evt_short", "payment_intent.succeeded", intent, cents - 1)
    )

    assert response.json() == {"status": "amount_mismatch"}
    assert await status_of(sessions, order_id) == OrderStatus.PENDING


async def test_canceled_payment_restocks_exactly_once_under_redelivery(
    sessions, fake_stripe, client
):
    order_id, intent, cents, product = await pending_order(sessions, stock=3, quantity=2)
    assert await stock_of(sessions, product) == 1
    payload = event("evt_cancel_1", "payment_intent.canceled", intent, 0)

    # Stripe can deliver the same event twice at once; only one may restock.
    responses = await asyncio.gather(*(post_event(client, payload) for _ in range(3)))

    assert sorted(r.json()["status"] for r in responses) == ["cancelled", "duplicate", "duplicate"]
    assert await status_of(sessions, order_id) == OrderStatus.CANCELLED
    assert await stock_of(sessions, product) == 3


async def test_late_success_cannot_reopen_a_cancelled_order(sessions, fake_stripe, client):
    order_id, intent, cents, _ = await pending_order(sessions)
    await post_event(client, event("evt_c", "payment_intent.canceled", intent, 0))

    late = await post_event(client, event("evt_s", "payment_intent.succeeded", intent, cents))

    assert late.json() == {"status": "already_cancelled"}
    assert await status_of(sessions, order_id) == OrderStatus.CANCELLED


async def test_failed_card_leaves_order_pending_for_a_retry(sessions, fake_stripe, client):
    order_id, intent, _, _ = await pending_order(sessions)

    response = await post_event(
        client, event("evt_fail", "payment_intent.payment_failed", intent, 0)
    )

    assert response.json() == {"status": "ignored"}
    assert await status_of(sessions, order_id) == OrderStatus.PENDING


async def test_forged_or_unsigned_events_are_rejected(sessions, fake_stripe, client):
    order_id, intent, cents, _ = await pending_order(sessions)
    payload = event("evt_forged", "payment_intent.succeeded", intent, cents)

    forged = await post_event(client, payload, signed(payload, secret="whsec_attacker"))
    unsigned = await client.post("/api/v1/payments/stripe/webhook", content=payload)

    assert forged.status_code == 400 and unsigned.status_code == 400
    assert await status_of(sessions, order_id) == OrderStatus.PENDING
    assert await scalar(sessions, select(func.count()).select_from(StripeEvent)) == 0
