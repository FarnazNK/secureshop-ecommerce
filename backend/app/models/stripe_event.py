"""Durable log of Stripe webhook events.

The webhook stores every verified event here *before* acting on it. Stripe's
event id is the primary key, so a redelivered event is recognised and skipped.
If processing fails, the row stays `failed` (with the error) and the scheduled
`payments retry-events` job processes it again: no paid queue needed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StripeEvent(Base):
    __table_args__ = (Index("ix_stripe_event_status_received", "status", "received_at"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # evt_...
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # received -> processed | failed (retried by the job) | ignored
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    outcome: Mapped[str | None] = mapped_column(String(60), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RateLimitBucket(Base):
    """Fixed-window request counters shared by every API instance.

    Used only when RATE_LIMIT_BACKEND=database. One upsert per request keeps
    the limit correct across serverless instances using the existing database.
    """

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger, nullable=False)  # epoch seconds
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
