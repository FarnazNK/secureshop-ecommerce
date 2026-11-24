"""Stripe Checkout integration.

Flow:
1. `POST /orders` creates a PENDING order (stock reserved, cart cleared) and a
   Stripe Checkout Session for it. The storefront redirects to the session URL,
   so card details never touch this API.
2. Stripe calls `POST /payments/webhook` (signature-verified):
   - `checkout.session.completed` / `async_payment_succeeded` with
     `payment_status == "paid"` -> order becomes PAID.
   - `checkout.session.expired` / `async_payment_failed` -> order becomes
     CANCELLED and its reserved stock is returned.
3. `POST /orders/{id}/sync-payment` re-reads the session from Stripe, so the
   order page is correct even if the webhook is delayed.

Every state change goes through `apply_checkout_session`, which is idempotent
and checks that the session belongs to the order and that the amount and
currency Stripe charged match the order total.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.order import Order, OrderItem, OrderStatus

log = get_logger(__name__)

# Stripe requires a Checkout Session to stay open for at least 30 minutes.
CHECKOUT_SESSION_MINUTES = 30

PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
FAILED_EVENTS = {"checkout.session.expired", "checkout.session.async_payment_failed"}


class PaymentError(Exception):
    """Raised when Stripe rejects a request or returns data we can't trust."""


def payments_enabled(settings: Settings) -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def is_test_mode(settings: Settings) -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY.startswith("sk_test_"))


def to_minor_units(amount: Decimal) -> int:
    """Dollars to cents without float rounding."""
    return int((amount * 100).quantize(Decimal("1")))


def field(obj: Any, key: str) -> Any:
    """Read a field from a StripeObject or a plain dict (StripeObject is not a dict in v12+)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    try:
        return obj[key]
    except (KeyError, TypeError):
        return getattr(obj, key, None)


async def _stripe_call(settings: Settings, fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking Stripe SDK call in a worker thread with the configured key."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except stripe.StripeError as exc:
        log.error("stripe.request_failed", error=str(exc), call=getattr(fn, "__qualname__", ""))
        raise PaymentError("payment provider error") from exc


async def create_checkout_session(
    settings: Settings,
    order: Order,
    *,
    customer_email: str | None,
    attempt: int = 0,
) -> tuple[str, str]:
    """Create a Checkout Session for `order` and return (session_id, url)."""
    currency = settings.STRIPE_CURRENCY.lower()
    base = settings.FRONTEND_URL.rstrip("/")
    line_items = [
        {
            "quantity": item.quantity,
            "price_data": {
                "currency": currency,
                "unit_amount": to_minor_units(item.unit_price),
                "product_data": {"name": item.product_name},
            },
        }
        for item in order.items
    ]
    expires_at = datetime.now(UTC) + timedelta(minutes=CHECKOUT_SESSION_MINUTES + 1)
    session = await _stripe_call(
        settings,
        stripe.checkout.Session.create,
        mode="payment",
        line_items=line_items,
        client_reference_id=str(order.id),
        customer_email=customer_email,
        metadata={"order_id": str(order.id), "order_number": order.order_number},
        payment_intent_data={
            "metadata": {"order_id": str(order.id), "order_number": order.order_number}
        },
        success_url=f"{base}/orders/{order.id}?checkout=success",
        cancel_url=f"{base}/orders/{order.id}?checkout=cancelled",
        expires_at=int(expires_at.timestamp()),
        # Safe retries: the same order + attempt never creates two sessions.
        idempotency_key=f"checkout-{order.id}-{attempt}",
    )
    session_id, url = field(session, "id"), field(session, "url")
    if not session_id or not url:
        raise PaymentError("payment provider returned an incomplete session")
    return str(session_id), str(url)


async def retrieve_checkout_session(settings: Settings, session_id: str) -> Any:
    return await _stripe_call(settings, stripe.checkout.Session.retrieve, session_id)


async def load_order_for_payment(db: AsyncSession, order_id: Any) -> Order | None:
    return await db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .with_for_update(of=Order)
    )


async def cancel_and_restock(order: Order) -> None:
    """Cancel a PENDING order and return its reserved stock."""
    if order.status != OrderStatus.PENDING:
        return
    for item in order.items:
        if item.product is not None:
            item.product.stock_quantity += item.quantity
    order.status = OrderStatus.CANCELLED


async def apply_checkout_session(
    order: Order,
    session: Any,
    *,
    settings: Settings,
    event_type: str | None = None,
) -> str:
    """Apply a Checkout Session's state to its order. Returns what happened.

    Idempotent: replaying the same webhook or syncing twice changes nothing.
    """
    session_id = field(session, "id")
    belongs = field(session, "client_reference_id") == str(order.id)
    if not belongs:
        log.warning("payment.session_mismatch", order_id=str(order.id), session_id=session_id)
        return "ignored_mismatch"

    payment_status = field(session, "payment_status")
    session_status = field(session, "status")

    if payment_status == "paid" and (event_type is None or event_type in PAID_EVENTS):
        if order.status == OrderStatus.PAID:
            return "already_paid"
        if order.status != OrderStatus.PENDING:
            # Paid after we cancelled (e.g. very late async payment): needs a human.
            log.error(
                "payment.paid_non_pending_order",
                order_id=str(order.id),
                status=str(order.status),
                session_id=session_id,
            )
            return "needs_review"
        expected = to_minor_units(order.total)
        amount = field(session, "amount_total")
        currency = (field(session, "currency") or "").lower()
        if amount != expected or currency != settings.STRIPE_CURRENCY.lower():
            log.error(
                "payment.amount_mismatch",
                order_id=str(order.id),
                expected=expected,
                amount=amount,
                currency=currency,
            )
            return "amount_mismatch"
        order.status = OrderStatus.PAID
        order.paid_at = datetime.now(UTC)
        order.stripe_checkout_session_id = session_id
        intent = field(session, "payment_intent")
        order.stripe_payment_intent_id = intent if isinstance(intent, str) else field(intent, "id")
        log.info("payment.order_paid", order_id=str(order.id), session_id=session_id)
        return "paid"

    expired = session_status == "expired" or event_type in FAILED_EVENTS
    if expired:
        # Only the order's current session may cancel it, so an unrelated or
        # outdated session can never cancel a live order.
        if session_id != order.stripe_checkout_session_id:
            return "ignored_stale_session"
        if order.status != OrderStatus.PENDING:
            return "already_final"
        await cancel_and_restock(order)
        log.info("payment.order_cancelled", order_id=str(order.id), session_id=session_id)
        return "cancelled"

    return "pending"
