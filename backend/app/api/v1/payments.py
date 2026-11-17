"""Stripe webhook: the only path that marks an order as paid.

Security properties:
- Every event's `Stripe-Signature` header is verified against
  STRIPE_WEBHOOK_SECRET over the raw request body (HMAC-SHA256 plus a
  timestamp tolerance against replays). Unsigned or tampered events get a 400.
- The endpoint is disabled (503) when no webhook secret is configured, so it
  can never run unauthenticated.
- The amount and currency Stripe received are checked against the order's
  server-side total before the order is marked paid.
- Handling is idempotent: Stripe retries deliveries, and replaying an event
  never pays, cancels or restocks an order twice.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.orders import to_stripe_amount
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.order import Order, OrderStatus
from app.models.product import Product

router = APIRouter()
log = get_logger(__name__)

CURRENCY = "usd"


def verify_event(payload: bytes, signature: str | None, secret: str) -> dict[str, Any]:
    """Return the event as a plain dict, or raise 400 if the signature is invalid."""
    if not signature:
        raise HTTPException(400, detail="missing Stripe-Signature header")
    try:
        stripe.Webhook.construct_event(payload, signature, secret)
        # Signature checked: work with the verified bytes as plain JSON so
        # the handler doesn't depend on stripe-python's object model.
        return json.loads(payload)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        log.warning("stripe.webhook_rejected", reason=type(exc).__name__)
        raise HTTPException(400, detail="invalid webhook signature") from exc


async def _locked_order(db: AsyncSession, payment_intent_id: str) -> Order | None:
    return await db.scalar(
        select(Order)
        .where(Order.stripe_payment_intent_id == payment_intent_id)
        .options(selectinload(Order.items))
        .with_for_update()
    )


async def _restock(db: AsyncSession, order: Order) -> None:
    ids = sorted({i.product_id for i in order.items if i.product_id is not None}, key=str)
    products = {
        p.id: p
        for p in (
            await db.scalars(
                select(Product)
                .where(Product.id.in_(ids))
                .order_by(Product.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    }
    for item in order.items:
        product = products.get(item.product_id) if item.product_id else None
        if product is not None:
            product.stock_quantity += item.quantity


async def apply_payment_event(db: AsyncSession, event: dict[str, Any]) -> str:
    """Apply a verified Stripe event to its order. Returns a short outcome label."""
    event_type = event["type"]
    intent = event["data"]["object"]

    if event_type not in {
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    }:
        return "ignored"

    order = await _locked_order(db, intent["id"])
    if order is None:
        log.warning("stripe.webhook_unknown_intent", intent_id=intent["id"], type=event_type)
        return "unknown_intent"

    if event_type == "payment_intent.succeeded":
        if order.status == OrderStatus.PAID:
            return "already_paid"
        if order.status != OrderStatus.PENDING:
            # E.g. paid after we cancelled it: needs a human (refund or reinstate).
            log.error(
                "stripe.payment_for_non_pending_order",
                order_number=order.order_number,
                status=str(order.status),
            )
            return "needs_review"
        received = intent.get("amount_received")
        currency = intent.get("currency")
        if received != to_stripe_amount(order.total) or currency != CURRENCY:
            log.error(
                "stripe.amount_mismatch",
                order_number=order.order_number,
                expected=to_stripe_amount(order.total),
                received=received,
                currency=currency,
            )
            return "amount_mismatch"
        order.status = OrderStatus.PAID
        await db.commit()
        log.info("order.paid", order_number=order.order_number)
        return "paid"

    if event_type == "payment_intent.payment_failed":
        # The customer can retry the same payment intent, so the order stays
        # PENDING and its stock stays reserved.
        log.info("order.payment_failed", order_number=order.order_number)
        return "payment_failed"

    # payment_intent.canceled: release the reserved stock exactly once.
    if order.status != OrderStatus.PENDING:
        return "already_closed"
    order.status = OrderStatus.CANCELLED
    await _restock(db, order)
    await db.commit()
    log.info("order.cancelled", order_number=order.order_number)
    return "cancelled"


@router.post("/webhook", summary="Stripe webhook (signature-verified)", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    secret = get_settings().STRIPE_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(503, detail="payments webhook not configured")

    # Signature is computed over the exact bytes Stripe sent, so read the raw
    # body. Never parse JSON first.
    payload = await request.body()
    event = verify_event(payload, request.headers.get("stripe-signature"), secret)
    outcome = await apply_payment_event(db, event)
    return {"status": outcome}
