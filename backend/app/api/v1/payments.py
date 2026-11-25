"""Payment endpoints: public config for the storefront, and the Stripe webhook."""

from __future__ import annotations

import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.order import PaymentConfigOut
from app.services import payments

router = APIRouter()
log = get_logger(__name__)

HANDLED_EVENTS = payments.PAID_EVENTS | payments.FAILED_EVENTS


@router.get("/config", response_model=PaymentConfigOut, summary="Payment settings for checkout")
async def payment_config() -> PaymentConfigOut:
    """Lets the storefront show 'Pay with Stripe (test mode)' or the demo checkout.
    Exposes no secrets."""
    settings = get_settings()
    return PaymentConfigOut(
        enabled=payments.payments_enabled(settings),
        test_mode=payments.is_test_mode(settings),
        currency=settings.STRIPE_CURRENCY.lower(),
    )


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    """Stripe → us. Authenticated by signature, not by user token.

    Returns 2xx for anything we understood (including events we deliberately
    ignore) so Stripe stops retrying; 4xx only for bad signatures or payloads.
    """
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, detail="webhook not configured")
    if not stripe_signature:
        raise HTTPException(400, detail="missing signature")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError as exc:
        log.warning("stripe.webhook_bad_signature")
        raise HTTPException(400, detail="invalid signature") from exc
    except ValueError as exc:
        raise HTTPException(400, detail="invalid payload") from exc

    event_type = payments.field(event, "type")
    if event_type not in HANDLED_EVENTS:
        return {"status": "ignored"}

    session = payments.field(payments.field(event, "data"), "object")
    reference = payments.field(session, "client_reference_id")
    try:
        order_id = uuid.UUID(str(reference))
    except ValueError:
        log.warning("stripe.webhook_unknown_reference", reference=reference)
        return {"status": "ignored"}

    order = await payments.load_order_for_payment(db, order_id)
    if order is None:
        log.warning("stripe.webhook_order_not_found", order_id=str(order_id))
        return {"status": "ignored"}

    outcome = await payments.apply_checkout_session(
        db, order, session, settings=settings, event_type=event_type
    )
    await db.commit()
    log.info(
        "stripe.webhook_handled",
        event_id=payments.field(event, "id"),
        event_type=event_type,
        order_id=str(order.id),
        outcome=outcome,
    )
    return {"status": outcome}
