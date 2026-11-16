"""Records that make checkout and payment processing safe to retry.

``IdempotencyKey`` ties a client-chosen key to the order its first request created, so a
retried checkout (double-click, mobile network retry) returns that order instead of placing
a second one. ``StripeEvent`` records every processed webhook event, so a redelivered event
changes nothing.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class IdempotencyKey(Base, UUIDMixin, TimestampMixin):
    """One row per (user, Idempotency-Key header). Written in the same transaction as the
    order it created, so a key exists if and only if its order does."""

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency_key_user_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 of the request body: the same key with a different body is a client bug.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("order.id", ondelete="CASCADE"), nullable=True
    )


class StripeEvent(Base, TimestampMixin):
    """A Stripe webhook event that has been processed. The primary key is Stripe's event id."""

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
