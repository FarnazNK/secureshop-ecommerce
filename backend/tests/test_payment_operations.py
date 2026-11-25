"""Webhook event log, retries, refunds, disputes and the scheduled jobs
(expire-stale, retry-events, reconcile). SQLite + faked Stripe network calls;
webhook signatures are verified for real."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import stripe
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.orders import refund_order
from app.jobs import payments as jobs
from app.models.order import Order, OrderStatus
from app.models.stripe_event import StripeEvent
from app.models.user import Role, User
from app.schemas.order import RefundRequest
from app.services import payments
from tests.payment_fixtures import FakeStripe, event, place_order, reload, signed, stock


def post_event(client: TestClient, body: dict[str, Any]):
    payload, signature = signed(body)
    return client.post(
        "/api/v1/payments/webhook", content=payload, headers={"Stripe-Signature": signature}
    )


def with_id(body: dict[str, Any], event_id: str) -> dict[str, Any]:
    return {**body, "id": event_id, "created": int(datetime.now(UTC).timestamp())}


async def paid_order(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> Order:
    response, _user, _product = await place_order(sessions)
    post_event(
        client,
        with_id(event("checkout.session.completed", fake_stripe.pay("cs_test_1")), "evt_paid"),
    )
    order = await reload(sessions, response.order.id)
    assert order.status == OrderStatus.PAID
    return order


async def stored(sessions: async_sessionmaker[AsyncSession], event_id: str) -> StripeEvent:
    async with sessions() as db:
        record = await db.get(StripeEvent, event_id)
        assert record is not None
        return record


# ------------------------------------------------------------------ event log
async def test_events_are_logged_and_duplicates_skipped(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await paid_order(client, fake_stripe, sessions)
    record = await stored(sessions, "evt_paid")
    assert (record.status, record.outcome, record.attempts) == ("processed", "paid", 1)

    again = post_event(
        client,
        with_id(event("checkout.session.completed", fake_stripe.sessions["cs_test_1"]), "evt_paid"),
    )
    assert again.json() == {"status": "duplicate"}


async def test_failed_processing_is_stored_and_retried_by_job(
    client: TestClient,
    fake_stripe: FakeStripe,
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _user, _product = await place_order(sessions)
    real = payments.process_event

    async def broken(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(payments, "process_event", broken)
    result = post_event(
        client,
        with_id(event("checkout.session.completed", fake_stripe.pay("cs_test_1")), "evt_flaky"),
    )
    # Stripe still gets a 2xx, so it doesn't pile up retries behind our failure.
    assert result.status_code == 200
    assert result.json() == {"status": "failed_will_retry"}
    record = await stored(sessions, "evt_flaky")
    assert record.status == "failed"
    assert "database hiccup" in (record.last_error or "")
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PENDING

    monkeypatch.setattr(payments, "process_event", real)
    async with sessions() as db:  # make it old enough for the retry job
        await db.execute(
            update(StripeEvent)
            .where(StripeEvent.id == "evt_flaky")
            .values(received_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await db.commit()
    summary = await jobs.retry_events(sessions)
    assert summary["outcomes"] == {"paid": 1}
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PAID
    assert (await stored(sessions, "evt_flaky")).status == "processed"


async def test_unhandled_event_types_are_not_stored(
    client: TestClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    result = post_event(
        client, {"id": "evt_other", "type": "customer.created", "data": {"object": {}}}
    )
    assert result.json() == {"status": "ignored"}
    async with sessions() as db:
        assert await db.get(StripeEvent, "evt_other") is None


# ------------------------------------------------------------ refunds & disputes
async def test_charge_refunded_webhook_partial_then_full(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    order = await paid_order(client, fake_stripe, sessions)  # total 25.00
    charge = {
        "object": "charge",
        "payment_intent": "pi_test_123",
        "amount_refunded": 1000,
        "refunded": False,
    }

    first = post_event(
        client, with_id({"type": "charge.refunded", "data": {"object": charge}}, "evt_r1")
    )
    assert first.json() == {"status": "partially_refunded"}
    partial = await reload(sessions, str(order.id))
    assert (partial.status, partial.amount_refunded) == (OrderStatus.PAID, Decimal("10.00"))

    full = {**charge, "amount_refunded": 2500, "refunded": True}
    second = post_event(
        client, with_id({"type": "charge.refunded", "data": {"object": full}}, "evt_r2")
    )
    assert second.json() == {"status": "refunded"}
    refunded = await reload(sessions, str(order.id))
    assert (refunded.status, refunded.amount_refunded) == (OrderStatus.REFUNDED, Decimal("25.00"))


async def test_dispute_webhook_flags_order(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    order = await paid_order(client, fake_stripe, sessions)
    dispute = {"object": "dispute", "payment_intent": "pi_test_123", "status": "needs_response"}
    result = post_event(
        client, with_id({"type": "charge.dispute.created", "data": {"object": dispute}}, "evt_d1")
    )
    assert result.json() == {"status": "dispute_needs_response"}
    assert (await reload(sessions, str(order.id))).dispute_status == "needs_response"


async def test_admin_refund_endpoint_refunds_once_per_click(
    client: TestClient,
    fake_stripe: FakeStripe,
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = await paid_order(client, fake_stripe, sessions)
    refunds: list[dict[str, Any]] = []

    def create_refund(**kwargs: Any) -> dict[str, Any]:
        refunds.append(kwargs)
        return {"id": "re_1", "status": "succeeded"}

    monkeypatch.setattr(stripe.Refund, "create", create_refund)
    admin = User(
        email="admin@example.com", password_hash="x", first_name="A", last_name="D", role=Role.ADMIN
    )

    async with sessions() as db:
        partial = await refund_order(
            str(order.id), RefundRequest(amount=Decimal("5.00")), _admin=admin, db=db
        )
    assert partial.amount_refunded == Decimal("5.00")
    assert partial.status == OrderStatus.PAID
    assert refunds[0]["amount"] == 500
    assert refunds[0]["payment_intent"] == "pi_test_123"

    async with sessions() as db:
        rest = await refund_order(str(order.id), RefundRequest(), _admin=admin, db=db)
    assert rest.status == OrderStatus.REFUNDED
    assert refunds[1]["amount"] == 2000
    # Different keys for the two different refunds; a retried click would reuse one.
    assert refunds[0]["idempotency_key"] != refunds[1]["idempotency_key"]

    async with sessions() as db:
        with pytest.raises(HTTPException) as exc:
            await refund_order(str(order.id), RefundRequest(), _admin=admin, db=db)
    assert exc.value.status_code == 409


async def test_refund_cannot_exceed_what_was_paid(
    client: TestClient, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    order = await paid_order(client, fake_stripe, sessions)
    admin = User(
        email="admin2@example.com",
        password_hash="x",
        first_name="A",
        last_name="D",
        role=Role.ADMIN,
    )
    async with sessions() as db:
        with pytest.raises(HTTPException) as exc:
            await refund_order(
                str(order.id), RefundRequest(amount=Decimal("99.00")), _admin=admin, db=db
            )
    assert exc.value.status_code == 422


# ----------------------------------------------------------------- scheduled jobs
async def age_order(
    sessions: async_sessionmaker[AsyncSession], order_id: str, minutes: int
) -> None:
    async with sessions() as db:
        await db.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order_id))
            .values(created_at=datetime.now(UTC) - timedelta(minutes=minutes))
        )
        await db.commit()


async def test_expire_stale_recovers_lost_webhooks(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    from app.core.config import get_settings

    expired_order, _u, product = await place_order(sessions)
    fake_stripe.expire("cs_test_1")
    await age_order(sessions, expired_order.order.id, minutes=60)

    summary = await jobs.expire_stale(sessions, get_settings())
    assert summary["outcomes"] == {"cancelled": 1}
    assert (await reload(sessions, expired_order.order.id)).status == OrderStatus.CANCELLED
    assert await stock(sessions, product) == 10  # stock returned


async def test_expire_stale_leaves_recent_orders_alone(
    stripe_env: None, fake_stripe: FakeStripe, sessions: async_sessionmaker[AsyncSession]
) -> None:
    from app.core.config import get_settings

    recent, _u, _p = await place_order(sessions)
    summary = await jobs.expire_stale(sessions, get_settings())
    assert summary["checked"] == 0
    assert (await reload(sessions, recent.order.id)).status == OrderStatus.PENDING


async def test_reconcile_fixes_missed_webhook_and_reports_unknown(
    stripe_env: None,
    fake_stripe: FakeStripe,
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    response, _u, _p = await place_order(sessions)
    paid = fake_stripe.pay("cs_test_1")  # paid in Stripe, webhook never arrived
    stranger = {**paid, "id": "cs_orphan", "client_reference_id": str(uuid.uuid4())}
    monkeypatch.setattr(jobs, "_list_completed_sessions", lambda _since: [paid, stranger])

    report = await jobs.reconcile(sessions, get_settings())
    assert report["fixed_missed_webhooks"] == [response.order.id]
    assert report["paid_in_stripe_but_no_order"] == ["cs_orphan"]
    assert report["needs_attention"] is True
    assert (await reload(sessions, response.order.id)).status == OrderStatus.PAID


async def test_run_without_stripe_only_retries_events(
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.core.config import get_settings

    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    code = await jobs.run("all", sessions)
    get_settings.cache_clear()
    out = capsys.readouterr().out
    assert code == 0
    assert "not configured" in out
    async with sessions() as db:
        assert (await db.scalars(select(StripeEvent))).all() == []
