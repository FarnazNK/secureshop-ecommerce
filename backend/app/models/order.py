"""Order models. Orders are immutable once created — items are snapshots
(name, price) so historical receipts stay accurate even if the catalog
changes later.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class OrderStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(Base, UUIDMixin, TimestampMixin):
    """A placed order. Once created, only `status` and timestamps mutate."""

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_order_user_idempotency_key"),
        # "My orders, newest first" and the stale-reservation sweeper.
        Index("ix_order_user_created", "user_id", "created_at"),
        Index("ix_order_status_created", "status", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Human-readable order number (e.g. "ORD-20260105-AB12CD"). Distinct
    # from the UUID id so we can put it on receipts without leaking the PK.
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Money breakdown — Numeric, never Float.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    shipping: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Stripe payment intent — populated when the order is paid. Indexed because
    # refund and dispute webhooks look orders up by it.
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    # Current Stripe Checkout Session. Replaced when the customer retries payment.
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Client-supplied Idempotency-Key for POST /orders. Unique per user, so a
    # retried or double-clicked checkout returns the first order, not a second one.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Refunds and disputes (chargebacks), kept in sync by Stripe webhooks.
    amount_refunded: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    dispute_status: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Free-form note from the customer (gift wrap, delivery instructions).
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base, UUIDMixin, TimestampMixin):
    """A line in an order. Captures product details at order time so the
    receipt is accurate even if the catalog changes."""

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product.id", ondelete="SET NULL"),
        nullable=True,  # nullable so deleted products don't break old orders
    )

    # Snapshots at order time.
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_slug: Mapped[str] = mapped_column(String(280), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
