"""Stripe webhook: the only way an order's payment status changes.

Stripe delivers events at least once, possibly out of order, and retries until it gets a
2xx. So each event is handled in one transaction that both records its id and applies its
effect: a redelivered event finds its id already recorded and changes nothing.

Order transitions only start from PENDING, so a late or repeated event can't move an order
backwards (for example, from CANCELLED to PAID).
"""

from __future__ import annotations

from typing import Annotated, Any

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.money import to_cents
from app.db.session import get_db
from app.models.order import Order, OrderStatus
from app.models.payment import StripeEvent
from app.models.product import Product

router = APIRouter()
log = get_logger(__name__)


@router.post(
    "/stripe/webhook",
    summary="Stripe webhook receiver",
    responses={
        400: {"description": "Missing or invalid Stripe-Signature"},
        503: {"description": "Webhook secret not configured"},
    },
)
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="webhooks not configured")
    if not stripe_signature:
        raise HTTPException(400, detail="missing Stripe-Signature header")

    # Verify against the raw bytes: re-serialized JSON would not match the signature.
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        log.warning("stripe.webhook_rejected", error=str(exc))
        raise HTTPException(400, detail="invalid signature") from exc

    recorded = await db.scalar(
        pg_insert(StripeEvent)
        .values(id=event["id"], type=event["type"])
        .on_conflict_do_nothing(index_elements=[StripeEvent.id])
        .returning(StripeEvent.id)
    )
    if recorded is None:
        log.info("stripe.webhook_duplicate", event_id=event["id"], type=event["type"])
        return {"status": "duplicate"}

    intent = event["data"]["object"]
    if event["type"] == "payment_intent.succeeded":
        outcome = await _mark_paid(db, intent)
    elif event["type"] == "payment_intent.canceled":
        outcome = await _cancel_and_restock(db, intent)
    else:
        # payment_intent.payment_failed is not final: the customer can retry the card on the
        # same intent. The order stays PENDING until the intent succeeds or is canceled.
        outcome = "ignored"

    await db.commit()
    log.info("stripe.webhook_processed", event_id=event["id"], type=event["type"], outcome=outcome)
    return {"status": outcome}


async def _mark_paid(db: AsyncSession, intent: Any) -> str:
    order = await db.scalar(
        select(Order).where(Order.stripe_payment_intent_id == intent["id"]).with_for_update()
    )
    if order is None:
        return "unknown_order"
    if order.status != OrderStatus.PENDING:
        return f"already_{order.status.value}"
    if intent["amount_received"] != to_cents(order.total) or intent["currency"] != "usd":
        # Never mark an order paid for the wrong amount; leave it for a human to check.
        log.error(
            "stripe.amount_mismatch",
            order_id=str(order.id),
            expected=to_cents(order.total),
            received=intent["amount_received"],
        )
        return "amount_mismatch"
    order.status = OrderStatus.PAID
    return "paid"


async def _cancel_and_restock(db: AsyncSession, intent: Any) -> str:
    order = await db.scalar(
        select(Order)
        .where(Order.stripe_payment_intent_id == intent["id"])
        .options(selectinload(Order.items))
        .with_for_update()
    )
    if order is None:
        return "unknown_order"
    if order.status != OrderStatus.PENDING:
        return f"already_{order.status.value}"
    order.status = OrderStatus.CANCELLED
    # Return the reserved stock. Same id order as checkout, so the two can't deadlock.
    for item in sorted(order.items, key=lambda line: str(line.product_id)):
        if item.product_id is None:
            continue  # product deleted since; nothing to restock
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock_quantity=Product.stock_quantity + item.quantity)
            .execution_options(synchronize_session=False)
        )
    return "cancelled"
