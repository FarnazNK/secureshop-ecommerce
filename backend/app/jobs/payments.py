"""Scheduled payment maintenance. Run by GitHub Actions (free), or by hand:

    python -m app.jobs.payments expire-stale    # orders stuck in PENDING
    python -m app.jobs.payments retry-events    # webhook events that failed
    python -m app.jobs.payments reconcile       # Stripe vs. database
    python -m app.jobs.payments all

Every command is idempotent and safe to run at any time, in any order, or
concurrently with the live webhook: they all go through the same locked,
idempotent state functions as the webhook itself.

Exit code 1 means something needs a human (an unresolved reconciliation
mismatch); the workflow run then shows as failed so you notice.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.models.order import Order, OrderStatus
from app.models.stripe_event import StripeEvent
from app.services import payments

log = get_logger(__name__)

# Checkout Sessions expire after ~31 minutes; give the webhook a few more.
STALE_AFTER = timedelta(minutes=payments.CHECKOUT_SESSION_MINUTES + 5)
RETRY_AFTER = timedelta(minutes=1)
MAX_EVENT_ATTEMPTS = 10
BATCH = 200


async def expire_stale(sessions: async_sessionmaker[AsyncSession], settings: Settings) -> dict:
    """Resolve PENDING orders whose Checkout Session should have finished.

    Covers lost or delayed webhooks: asks Stripe for the session's real state
    and applies it (paid -> PAID; expired -> CANCELLED with stock returned).
    """
    cutoff = datetime.now(UTC) - STALE_AFTER
    async with sessions() as db:
        ids = list(
            await db.scalars(
                select(Order.id)
                .where(
                    Order.status == OrderStatus.PENDING,
                    Order.stripe_checkout_session_id.is_not(None),
                    Order.created_at < cutoff,
                )
                .order_by(Order.created_at)
                .limit(BATCH)
            )
        )
    summary: dict[str, int] = {}
    for order_id in ids:
        async with sessions() as db:
            order = await payments.load_order_for_payment(db, order_id)
            if order is None or order.status != OrderStatus.PENDING:
                continue
            session = await payments.retrieve_checkout_session(
                settings, order.stripe_checkout_session_id
            )
            outcome = await payments.apply_checkout_session(db, order, session, settings=settings)
            await db.commit()
        summary[outcome] = summary.get(outcome, 0) + 1
    return {"checked": len(ids), "outcomes": summary}


async def retry_events(sessions: async_sessionmaker[AsyncSession]) -> dict:
    """Re-process webhook events that were stored but failed (or never finished)."""
    cutoff = datetime.now(UTC) - RETRY_AFTER
    async with sessions() as db:
        ids = list(
            await db.scalars(
                select(StripeEvent.id)
                .where(
                    StripeEvent.status.in_(("received", "failed")),
                    StripeEvent.received_at < cutoff,
                    StripeEvent.attempts < MAX_EVENT_ATTEMPTS,
                )
                .order_by(StripeEvent.received_at)
                .limit(BATCH)
            )
        )
    outcomes: dict[str, int] = {}
    for event_id in ids:
        async with sessions() as db:
            record = await db.get(StripeEvent, event_id, with_for_update=True)
            if record is None or record.status not in {"received", "failed"}:
                continue
            outcome = await payments.process_stored_event(db, record, get_settings())
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    async with sessions() as db:
        gave_up = list(
            await db.scalars(
                select(StripeEvent.id).where(
                    StripeEvent.status == "failed",
                    StripeEvent.attempts >= MAX_EVENT_ATTEMPTS,
                )
            )
        )
    return {"retried": len(ids), "outcomes": outcomes, "gave_up": gave_up}


def _list_completed_sessions(since: datetime) -> list[Any]:
    """Runs inside the breaker-protected Stripe call (one thread, all pages)."""
    pages = stripe.checkout.Session.list(
        created={"gte": int(since.timestamp())}, status="complete", limit=100
    )
    return list(pages.auto_paging_iter())


async def reconcile(
    sessions: async_sessionmaker[AsyncSession], settings: Settings, *, hours: int = 48
) -> dict:
    """Compare Stripe's completed payments with our orders for the last `hours`.

    - paid in Stripe, not PAID here  -> fixed automatically (missed webhook)
    - paid in Stripe, no such order  -> reported (needs a human)
    - PAID here, not paid in Stripe  -> reported (needs a human)
    """
    since = datetime.now(UTC) - timedelta(hours=hours)
    stripe_sessions = await payments._stripe_call(settings, _list_completed_sessions, since)
    paid_in_stripe = {
        payments.field(s, "client_reference_id"): s
        for s in stripe_sessions
        if payments.field(s, "payment_status") == "paid"
    }
    fixed: list[str] = []
    unknown_in_db: list[str] = []
    for reference, session in paid_in_stripe.items():
        async with sessions() as db:
            try:
                order_id = uuid.UUID(str(reference))
            except ValueError:
                unknown_in_db.append(str(payments.field(session, "id")))
                continue
            order = await payments.load_order_for_payment(db, order_id)
            if order is None:
                unknown_in_db.append(str(payments.field(session, "id")))
                continue
            if order.status == OrderStatus.PENDING:
                outcome = await payments.apply_checkout_session(
                    db, order, session, settings=settings
                )
                await db.commit()
                if outcome == "paid":
                    fixed.append(str(order.id))

    async with sessions() as db:
        paid_here = list(
            await db.scalars(
                select(Order.id).where(
                    Order.status == OrderStatus.PAID,
                    Order.paid_at >= since,
                    Order.stripe_checkout_session_id.is_not(None),
                )
            )
        )
    not_paid_in_stripe = [str(i) for i in paid_here if str(i) not in paid_in_stripe]
    return {
        "window_hours": hours,
        "stripe_paid_sessions": len(paid_in_stripe),
        "fixed_missed_webhooks": fixed,
        "paid_in_stripe_but_no_order": unknown_in_db,
        "paid_here_but_not_in_stripe": not_paid_in_stripe,
        "needs_attention": bool(unknown_in_db or not_paid_in_stripe),
    }


async def run(command: str, sessions: async_sessionmaker[AsyncSession] | None = None) -> int:
    settings = get_settings()
    if sessions is None:
        from app.db.session import async_session_maker

        sessions = async_session_maker
    report: dict[str, Any] = {"command": command, "at": datetime.now(UTC).isoformat()}
    if command in {"retry-events", "all"}:
        report["retry_events"] = await retry_events(sessions)
    if not payments.payments_enabled(settings):
        report["stripe"] = "not configured; skipped Stripe checks"
    else:
        if command in {"expire-stale", "all"}:
            report["expire_stale"] = await expire_stale(sessions, settings)
        if command in {"reconcile", "all"}:
            report["reconcile"] = await reconcile(sessions, settings)
    print(json.dumps(report, indent=2, default=str))
    needs_attention = report.get("reconcile", {}).get("needs_attention") or bool(
        report.get("retry_events", {}).get("gave_up")
    )
    return 1 if needs_attention else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["expire-stale", "retry-events", "reconcile", "all"])
    args = parser.parse_args()
    configure_logging()
    sys.exit(asyncio.run(run(args.command)))


if __name__ == "__main__":
    main()
