"""Order endpoints. Creating an order:
1. Validates the cart (non-empty, all items in stock at current quantities).
2. Snapshots prices/names into OrderItems.
3. Creates a Stripe payment intent (if Stripe is configured).
4. Clears the cart.

The order starts in PENDING. Stripe webhook flips it to PAID; that webhook
handler is in `app/api/v1/stripe_webhook.py` (omitted here for brevity).
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
                "product_slug": item.product_slug,
                "unit_price": item.unit_price,
                "quantity": item.quantity,
                "line_total": item.line_total,
            }
            for item in order.items
        ],
        notes=order.notes,
        created_at=order.created_at.isoformat(),
    )


@router.post(
    "",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order from the current cart",
)
async def create_order(
    payload: CreateOrderRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateOrderResponse:
    settings = get_settings()

    # Load cart with everything we need.
    cart = await db.scalar(
        select(Cart)
        .where(Cart.user_id == user.id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    if cart is None or not cart.items:
        raise HTTPException(400, detail="cart is empty")

    # Re-validate stock at order time. Stock could have changed since the
    # item was added to the cart.
    for item in cart.items:
        if item.product is None or not item.product.is_active:
            raise HTTPException(409, detail=f"product {item.product_id} is no longer available")
        if item.product.stock_quantity < item.quantity:
            raise HTTPException(
                409,
                detail=f"insufficient stock for {item.product.name}",
            )

    subtotal = cart.subtotal
    tax = (subtotal * Decimal("0.0")).quantize(Decimal("0.01"))  # placeholder
    shipping = Decimal("0.00")  # placeholder — flat rate or carrier API in real life
    total = subtotal + tax + shipping

    order = Order(
        user_id=user.id,
        order_number=_generate_order_number(),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        total=total,
        notes=payload.notes,
    )
    for cart_item in cart.items:
        product = cart_item.product
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                unit_price=cart_item.unit_price,
                quantity=cart_item.quantity,
            )
        )
        # Decrement stock. Race conditions (two carts buying the last unit
        # at once) need DB-level row locks for production; out of scope here.
        product.stock_quantity -= cart_item.quantity

    db.add(order)

    # Stripe payment intent (only if configured). Creating the intent before
    # commit means we avoid orphan orders if Stripe rejects.
    payment_intent_secret: str | None = None
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(total * 100),  # Stripe expects cents
                currency="usd",
                metadata={
                    "order_number": order.order_number,
                    "user_id": str(user.id),
                },
                # idempotency_key would go here in real prod
            )
            order.stripe_payment_intent_id = intent.id
            payment_intent_secret = intent.client_secret
        except stripe.error.StripeError as exc:
            log.error("stripe.payment_intent_failed", error=str(exc))
            raise HTTPException(502, detail="payment provider error") from exc

    # Clear cart only after we're sure the order is going through.
    for cart_item in list(cart.items):
        await db.delete(cart_item)

    await db.commit()
    await db.refresh(order, ["items"])
    log.info("order.created", order_id=str(order.id), order_number=order.order_number)

    return CreateOrderResponse(
        order=_to_order_out(order),
        payment_intent_client_secret=payment_intent_secret,
    )


@router.get("", response_model=list[OrderOut])
async def list_orders(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OrderOut]:
    """List the current user's orders, newest first."""
    orders = (
        await db.scalars(
            select(Order)
            .where(Order.user_id == user.id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        )
    ).all()
    return [_to_order_out(o) for o in orders]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderOut:
    try:
        oid = uuid.UUID(order_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid order_id") from exc

    order = await db.scalar(
        select(Order)
        .where(Order.id == oid, Order.user_id == user.id)
        .options(selectinload(Order.items))
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order not found")
    return _to_order_out(order)
