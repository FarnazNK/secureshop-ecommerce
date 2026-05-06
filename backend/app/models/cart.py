"""Cart models.

One cart per authenticated user. Guest carts live in localStorage on the
frontend and are merged into the server cart on login (handled in the
auth flow, not here).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class Cart(Base, UUIDMixin, TimestampMixin):
    """Per-user shopping cart. Subtotal is computed on read, not stored."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="cart")
    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    @property
    def subtotal(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0.00"))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)


class CartItem(Base, UUIDMixin, TimestampMixin):
    """A line item in a cart. (cart_id, product_id) is unique — quantity
    is bumped on re-add, not duplicated."""

    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),)

    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cart.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Price snapshot at add-to-cart time. Cart total respects the snapshot
    # until the item is removed/updated, so a price change mid-shopping
    # doesn't surprise the user.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
