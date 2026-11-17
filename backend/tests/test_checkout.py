"""Secure checkout: idempotent order creation, server-side repricing, stock
checks, and the signature-verified Stripe webhook."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.api.v1.cart import add_to_cart
from app.api.v1.orders import create_order, to_stripe_amount
from app.api.v1.payments import apply_payment_event, stripe_webhook
from app.core.config import get_settings
from app.db.base import Base
from app.models.cart import Cart
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import AddToCartRequest, CreateOrderRequest

WEBHOOK_SECRET = "whsec_test_secret_for_signature_checks"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        yield session
    await engine.dispose()


async def _seed(db, stock: int = 5, price: str = "20.00"):
    user = User(
        email="buyer@example.com",
        password_hash="unused-test-hash",
        first_name="Buyer",
        last_name="Test",
    )
    product = Product(
        name="Widget",
        slug="widget",
        description="Synthetic test product",
        price=Decimal(price),
        stock_quantity=stock,
        images=[],
    )
    db.add_all([user, product])
    await db.commit()
    return user, product


async def _checkout(db, user, key: str | None = None):
    # FastAPI injects a Response with no status; the route's default (201)
    # applies unless the handler overrides it.
    response = Response()
    response.status_code = None
    result = await create_order(
        CreateOrderRequest(notes=None), response, user, db, idempotency_key=key
    )
    return result, response.status_code or 201


@pytest.mark.asyncio
async def test_checkout_creates_pending_order_and_reserves_stock(db):
    user, product = await _seed(db)
    await add_to_cart(AddToCartRequest(product_id=str(product.id), quantity=2), user, db)

    result, code = await _checkout(db, user)

    assert code == 201
    assert result.order.status == OrderStatus.PENDING
    assert result.order.total == Decimal("40.00")
    await db.refresh(product)
    assert product.stock_quantity == 3
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))
    await db.refresh(cart, ["items"])
    assert cart.items == []


@pytest.mark.asyncio
async def test_retried_checkout_with_same_key_returns_original_order(db):
    user, product = await _seed(db)
    await add_to_cart(AddToCartRequest(product_id=str(product.id), quantity=1), user, db)

    first, first_code = await _checkout(db, user, key="checkout-key-0001")
    second, second_code = await _checkout(db, user, key="checkout-key-0001")

    assert (first_code, second_code) == (201, 200)
    assert second.order.id == first.order.id
    assert len((await db.scalars(select(Order))).all()) == 1
    await db.refresh(product)
    assert product.stock_quantity == 4  # decremented once, not twice


@pytest.mark.asyncio
async def test_checkout_rejects_stale_cart_price_and_reprices_cart(db):
    user, product = await _seed(db, price="20.00")
    await add_to_cart(AddToCartRequest(product_id=str(product.id), quantity=1), user, db)
    product.price = Decimal("25.00")
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await _checkout(db, user)
    assert exc.value.status_code == 409

    # Cart now shows the real price; the next checkout charges it.
    result, _ = await _checkout(db, user)
    assert result.order.total == Decimal("25.00")


@pytest.mark.asyncio
async def test_checkout_rejects_insufficient_stock(db):
    user, product = await _seed(db, stock=3)
    await add_to_cart(AddToCartRequest(product_id=str(product.id), quantity=3), user, db)
    product.stock_quantity = 1
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await _checkout(db, user)
    assert exc.value.status_code == 409
    assert (await db.scalars(select(Order))).all() == []


def test_stripe_amount_uses_exact_cents():
    assert to_stripe_amount(Decimal("19.99")) == 1999
    assert to_stripe_amount(Decimal("0.10")) == 10


# --- Webhook ---


async def _pending_order(db, intent_id: str = "pi_test_123"):
    user, product = await _seed(db, stock=5)
    await add_to_cart(AddToCartRequest(product_id=str(product.id), quantity=2), user, db)
    await _checkout(db, user)
    order = await db.scalar(select(Order))
    order.stripe_payment_intent_id = intent_id
    await db.commit()
    return order, product


def _event(event_type: str, intent_id: str = "pi_test_123", **intent) -> dict:
    return {"type": event_type, "data": {"object": {"id": intent_id, **intent}}}


@pytest.mark.asyncio
async def test_succeeded_event_marks_order_paid_once(db):
    order, _ = await _pending_order(db)
    event = _event("payment_intent.succeeded", amount_received=4000, currency="usd")

    assert await apply_payment_event(db, event) == "paid"
    assert await apply_payment_event(db, event) == "already_paid"  # Stripe retry
    await db.refresh(order)
    assert order.status == OrderStatus.PAID


@pytest.mark.asyncio
async def test_succeeded_event_with_wrong_amount_does_not_pay(db):
    order, _ = await _pending_order(db)
    event = _event("payment_intent.succeeded", amount_received=100, currency="usd")

    assert await apply_payment_event(db, event) == "amount_mismatch"
    await db.refresh(order)
    assert order.status == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_canceled_event_cancels_and_restocks_once(db):
    order, product = await _pending_order(db)
    await db.refresh(product)
    assert product.stock_quantity == 3

    event = _event("payment_intent.canceled")
    assert await apply_payment_event(db, event) == "cancelled"
    assert await apply_payment_event(db, event) == "already_closed"
    await db.refresh(order)
    await db.refresh(product)
    assert order.status == OrderStatus.CANCELLED
    assert product.stock_quantity == 5


@pytest.mark.asyncio
async def test_failed_payment_keeps_order_pending_for_retry(db):
    order, _ = await _pending_order(db)
    assert await apply_payment_event(db, _event("payment_intent.payment_failed")) == (
        "payment_failed"
    )
    await db.refresh(order)
    assert order.status == OrderStatus.PENDING


def _signed_request(payload: bytes, secret: str = WEBHOOK_SECRET, signature: str | None = None):
    if signature is None:
        timestamp = int(time.time())
        mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256)
        signature = f"t={timestamp},v1={mac.hexdigest()}"

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/payments/webhook",
        "headers": [(b"stripe-signature", signature.encode())],
    }
    return Request(scope, receive)


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_webhook_accepts_correctly_signed_event(db, webhook_secret):
    order, _ = await _pending_order(db)
    payload = json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            **_event("payment_intent.succeeded", amount_received=4000, currency="usd"),
        }
    ).encode()

    assert await stripe_webhook(_signed_request(payload), db) == {"status": "paid"}


@pytest.mark.asyncio
async def test_webhook_rejects_forged_signature(db, webhook_secret):
    order, _ = await _pending_order(db)
    payload = json.dumps(
        {
            "id": "evt_forged",
            "object": "event",
            **_event("payment_intent.succeeded", amount_received=4000, currency="usd"),
        }
    ).encode()

    with pytest.raises(HTTPException) as exc:
        await stripe_webhook(_signed_request(payload, secret="whsec_attacker_guess"), db)
    assert exc.value.status_code == 400
    await db.refresh(order)
    assert order.status == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_webhook_disabled_without_secret(db):
    get_settings.cache_clear()
    assert get_settings().STRIPE_WEBHOOK_SECRET is None
    with pytest.raises(HTTPException) as exc:
        await stripe_webhook(_signed_request(b"{}"), db)
    assert exc.value.status_code == 503
