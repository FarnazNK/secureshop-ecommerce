"""Payment endpoints: public config for the storefront, and the Stripe webhook."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.stripe_event import StripeEvent
from app.schemas.order import PaymentConfigOut
from app.services import payments

router = APIRouter()
log = get_logger(__name__)


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
    """Stripe -> us. Authenticated by signature, not by user token.

    1. Verify the signature (400 if forged or malformed).
    2. Save the event in `stripe_event` (its id is the primary key, so a
       redelivery is recognised) and commit: the event is now durable.
    3. Process it. If processing fails we still answer 200: the event is
       stored as `failed` and the scheduled retry job processes it again, so
       Stripe's own retries never pile up behind a slow or broken handler.
    """
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, detail="webhook not configured")
    if not stripe_signature:
        raise HTTPException(400, detail="missing signature")

    payload = await request.body()
    try:
        stripe.Webhook.construct_event(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError as exc:
        log.warning("stripe.webhook_bad_signature")
        raise HTTPException(400, detail="invalid signature") from exc
    except ValueError as exc:
        raise HTTPException(400, detail="invalid payload") from exc

    event = json.loads(payload)  # verified above; keep it as plain JSON
    event_id, event_type = str(event.get("id")), str(event.get("type"))
    if event_type not in payments.HANDLED_EVENTS:
        return {"status": "ignored"}

    record = await db.get(StripeEvent, event_id, with_for_update=True)
    if record is not None and record.status in {"processed", "ignored"}:
        return {"status": "duplicate"}
    if record is None:
        created = event.get("created")
        record = StripeEvent(
            id=event_id,
            type=event_type,
            payload=event,
            status="received",
            attempts=0,
            stripe_created_at=datetime.fromtimestamp(created, UTC)
            if isinstance(created, int)
            else None,
        )
        db.add(record)
        try:
            await db.commit()
        except IntegrityError:
            # The same event is being handled concurrently (Stripe retry race).
            await db.rollback()
            return {"status": "duplicate"}

    outcome = await payments.process_stored_event(db, record, settings)
    return {"status": outcome}
