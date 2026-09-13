"""Order endpoints. Creating an order:
1. Validates the cart (non-empty, all items in stock at current quantities).
2. Snapshots prices/names into OrderItems.
3. Creates a Stripe payment intent (if Stripe is configured).
4. Clears the cart.

The order starts in PENDING. A production Stripe webhook would transition
it to PAID; that handler is intentionally not implemented in this portfolio version.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC
from decimal import Decimal
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User
from app.schemas.order import CreateOrderRequest, CreateOrderResponse, OrderOut

router = APIRouter()
log = get_logger(__name__)


def _generate_order_number() -> str:
    """Human-readable order number. Distinct from the UUID PK so we can
    print it on receipts without leaking internal IDs."""
    from datetime import datetime

    now = datetime.now(UTC)
    return f"ORD-{now.strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def _to_order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        order_number=order.order_number,
        status=order.status,
        subtotal=order.subtotal,
        tax=order.tax,
        shipping=order.shipping,
        total=order.total,
        items=[
            {
                "id": str(item.id),
                "product_id": str(item.product_id) if item.product_id else None,
                "product_name": item.product_name,
