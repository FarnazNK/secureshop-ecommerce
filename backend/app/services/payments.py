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
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import stripe
from prometheus_client import Counter, Histogram
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product

log = get_logger(__name__)

# Stripe requires a Checkout Session to stay open for at least 30 minutes.
CHECKOUT_SESSION_MINUTES = 30

PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
FAILED_EVENTS = {"checkout.session.expired", "checkout.session.async_payment_failed"}


class PaymentError(Exception):
    """Raised when Stripe rejects a request or returns data we can't trust."""


class PaymentUnavailableError(PaymentError):
    """Stripe is failing or slow right now; callers should answer 503 and keep
    the customer's cart so they can try again shortly."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("payments are temporarily unavailable")
        self.retry_after = retry_after


STRIPE_CALLS = Counter("secureshop_stripe_calls_total", "Stripe API calls by outcome", ["outcome"])
STRIPE_LATENCY = Histogram("secureshop_stripe_call_seconds", "Stripe API call latency")

_breaker: CircuitBreaker | None = None
_http_client: Any = None


def get_breaker(settings: Settings) -> CircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = CircuitBreaker(
            "stripe",
            failure_threshold=settings.STRIPE_BREAKER_FAILURE_THRESHOLD,
            window_seconds=settings.STRIPE_BREAKER_WINDOW_SECONDS,
            reset_timeout_seconds=settings.STRIPE_BREAKER_RESET_SECONDS,
        )
    return _breaker


def _configure_stripe(settings: Settings) -> None:
    """Short timeout + bounded retries. Retries are safe because every write
    we send carries an idempotency key."""
    global _http_client
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.max_network_retries = settings.STRIPE_MAX_NETWORK_RETRIES
    if (
        _http_client is None
        or getattr(_http_client, "_timeout", None) != settings.STRIPE_TIMEOUT_SECONDS
    ):
        _http_client = stripe.RequestsClient(timeout=settings.STRIPE_TIMEOUT_SECONDS)
        stripe.default_http_client = _http_client


def is_transient(exc: Exception) -> bool:
    """Errors that mean Stripe is unhealthy (count toward the breaker), as
    opposed to Stripe answering 'no' to a bad request (it is healthy)."""
    if isinstance(exc, stripe.APIConnectionError | stripe.RateLimitError):
        return True
    status = getattr(exc, "http_status", None)
    return isinstance(exc, stripe.APIError) or (status is not None and status >= 500)


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
    """Run a blocking Stripe SDK call in a worker thread, behind the circuit breaker."""
    _configure_stripe(settings)
    breaker = get_breaker(settings)
    try:
        breaker.before_call()
    except CircuitOpenError as exc:
        STRIPE_CALLS.labels("rejected_open_circuit").inc()
        raise PaymentUnavailableError(exc.retry_after) from exc
    started = time.monotonic()
    try:
        result = await asyncio.to_thread(fn, *args, **kwargs)
    except stripe.StripeError as exc:
        STRIPE_LATENCY.observe(time.monotonic() - started)
        call = getattr(fn, "__qualname__", "")
        if is_transient(exc):
            breaker.record_failure()
            STRIPE_CALLS.labels("transient_error").inc()
            log.error("stripe.unavailable", error=str(exc), call=call, circuit=breaker.state.name)
            raise PaymentUnavailableError(int(settings.STRIPE_BREAKER_RESET_SECONDS)) from exc
        breaker.record_success()  # Stripe answered; the request itself was rejected
        STRIPE_CALLS.labels("rejected_by_stripe").inc()
        log.error("stripe.request_failed", error=str(exc), call=call)
        raise PaymentError("payment provider error") from exc
    except BaseException:
        breaker.abandon_trial()  # cancelled/unexpected: don't leave a half-open trial stuck
        raise
    STRIPE_LATENCY.observe(time.monotonic() - started)
    breaker.record_success()
    STRIPE_CALLS.labels("ok").inc()
    return result


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


async def cancel_and_restock(db: AsyncSession, order: Order) -> None:
    """Cancel a PENDING order and return its reserved stock.

    Stock is returned with an atomic `stock = stock + n` UPDATE, never
    read-modify-write, so a concurrent purchase of the same product can't be
    lost. Products are updated in id order so concurrent transactions lock rows
    in the same order (no deadlocks)."""
    if order.status != OrderStatus.PENDING:
        return
    for item in sorted(order.items, key=lambda i: str(i.product_id)):
        if item.product_id is None:
            continue
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock_quantity=Product.stock_quantity + item.quantity)
            .execution_options(synchronize_session=False)
        )
    order.status = OrderStatus.CANCELLED


async def apply_checkout_session(
    db: AsyncSession,
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
        await cancel_and_restock(db, order)
        log.info("payment.order_cancelled", order_id=str(order.id), session_id=session_id)
        return "cancelled"

    return "pending"


# ---------------------------------------------------------------------------
# Refunds and disputes
# ---------------------------------------------------------------------------
REFUND_EVENTS = {"charge.refunded"}
DISPUTE_EVENTS = {"charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed"}
HANDLED_EVENTS = PAID_EVENTS | FAILED_EVENTS | REFUND_EVENTS | DISPUTE_EVENTS
REFUNDABLE = {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED}

PAYMENT_OUTCOMES = Counter(
    "secureshop_payment_events_total",
    "Processed Stripe events by type and outcome",
    ["type", "outcome"],
)
WEBHOOK_LAG = Histogram(
    "secureshop_webhook_lag_seconds",
    "Time from Stripe creating an event to us processing it",
    buckets=(1, 5, 15, 60, 300, 900, 3600, 21600, 86400),
)


def from_minor_units(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


async def load_order_by_payment_intent(db: AsyncSession, intent_id: str) -> Order | None:
    return await db.scalar(
        select(Order).where(Order.stripe_payment_intent_id == intent_id).with_for_update()
    )


def apply_refund(order: Order, charge: Any) -> str:
    """Mirror Stripe's refunded amount onto the order (absolute value, so
    replays and out-of-order events converge on the same state)."""
    refunded = from_minor_units(int(field(charge, "amount_refunded") or 0))
    if refunded <= order.amount_refunded and order.status == OrderStatus.REFUNDED:
        return "already_refunded"
    order.amount_refunded = refunded
    if field(charge, "refunded") or refunded >= order.total:
        order.status = OrderStatus.REFUNDED
        return "refunded"
    return "partially_refunded"


def apply_dispute(order: Order, dispute: Any) -> str:
    status = str(field(dispute, "status") or "unknown")
    order.dispute_status = status
    if status == "lost":
        log.error("payment.dispute_lost", order_id=str(order.id))
    else:
        log.warning("payment.dispute", order_id=str(order.id), status=status)
    return f"dispute_{status}"


async def create_refund(
    settings: Settings,
    order: Order,
    *,
    amount_cents: int,
    reason: str | None,
) -> Any:
    """Refund through Stripe. The key includes what was already refunded, so a
    retried click can't refund twice but a later second partial refund can."""
    already = to_minor_units(order.amount_refunded)
    params: dict[str, Any] = {
        "payment_intent": order.stripe_payment_intent_id,
        "amount": amount_cents,
        "metadata": {"order_id": str(order.id), "order_number": order.order_number},
        "idempotency_key": f"refund-{order.id}-{already}-{amount_cents}",
    }
    if reason:
        params["reason"] = reason
    return await _stripe_call(settings, stripe.Refund.create, **params)


# ---------------------------------------------------------------------------
# One entry point for every handled event (webhook, retry job, reconciliation)
# ---------------------------------------------------------------------------
async def process_event(db: AsyncSession, settings: Settings, event: dict[str, Any]) -> str:
    """Apply a verified Stripe event. Idempotent; the caller commits."""
    event_type = str(event.get("type"))
    obj = (event.get("data") or {}).get("object") or {}
    created = event.get("created")
    if isinstance(created, int):
        WEBHOOK_LAG.observe(max(0.0, datetime.now(UTC).timestamp() - created))

    if event_type in PAID_EVENTS | FAILED_EVENTS:
        reference = field(obj, "client_reference_id")
        try:
            order_id = uuid.UUID(str(reference))
        except ValueError:
            outcome = "ignored_unknown_reference"
        else:
            order = await load_order_for_payment(db, order_id)
            outcome = (
                "ignored_order_not_found"
                if order is None
                else await apply_checkout_session(
                    db, order, obj, settings=settings, event_type=event_type
                )
            )
    elif event_type in REFUND_EVENTS | DISPUTE_EVENTS:
        intent = field(obj, "payment_intent")
        order = await load_order_by_payment_intent(db, str(intent)) if intent else None
        if order is None:
            outcome = "ignored_order_not_found"
        elif event_type in REFUND_EVENTS:
            outcome = apply_refund(order, obj)
        else:
            outcome = apply_dispute(order, obj)
    else:
        outcome = "ignored_type"
    PAYMENT_OUTCOMES.labels(event_type, outcome).inc()
    return outcome


async def process_stored_event(db: AsyncSession, record: Any, settings: Settings) -> str:
    """Process one stored `StripeEvent` and record the result. Never raises:
    a failure is saved on the row for the scheduled retry job."""
    event_id = record.id
    try:
        outcome = await process_event(db, settings, record.payload)
    except Exception as exc:
        await db.rollback()
        failed = await db.get(type(record), event_id)
        if failed is not None:
            failed.status = "failed"
            failed.attempts += 1
            failed.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            await db.commit()
        log.error("stripe.webhook_processing_failed", event_id=event_id, error=str(exc))
        return "failed_will_retry"
    record.status = "ignored" if outcome.startswith("ignored") else "processed"
    record.outcome = outcome
    record.attempts += 1
    record.last_error = None
    record.processed_at = datetime.now(UTC)
    await db.commit()
    log.info("stripe.webhook_handled", event_id=event_id, event_type=record.type, outcome=outcome)
    return outcome
