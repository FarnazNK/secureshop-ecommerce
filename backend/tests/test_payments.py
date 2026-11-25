"""Stripe Checkout flow: order creation, signed webhooks, retries and sync.

Runs against an in-memory SQLite database. Stripe's network calls are replaced
with fakes, but webhook signatures are generated and verified for real with
the Stripe SDK, so the security check is exercised end to end.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.orders import (
    create_order,
    create_order_checkout_session,
    sync_order_payment,
)
from app.models.cart import CartItem
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.order import CreateOrderRequest
from tests.payment_fixtures import (
    FakeStripe,
    event,
    place_order,
    reload,
    seed_cart,
    signed,
    stock,
)


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
    # Recognised by its event id in the stripe_event log; not processed twice.
    assert replay.json() == {"status": "duplicate"}


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
