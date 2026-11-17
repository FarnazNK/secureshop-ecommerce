"""Order endpoints. Creating an order (secure checkout):
1. Honors an optional `Idempotency-Key` header, so a retried or double-clicked
   checkout returns the original order instead of creating a second one.
2. Locks the product rows (`SELECT ... FOR UPDATE`) and re-validates the cart:
   non-empty, products still active, enough stock, prices unchanged.
3. Snapshots prices/names into OrderItems and decrements stock under the lock.
4. Creates a Stripe payment intent server-side (if Stripe is configured), with a
   Stripe idempotency key, so the amount is never taken from the client.
5. Clears the cart.

The order starts in PENDING. The signed Stripe webhook in `payments.py` moves
it to PAID, or to CANCELLED (restocking items) if the payment fails.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC
from decimal import Decimal
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    IDEMPOTENCY_KEY_PATTERN,
    CreateOrderRequest,
    CreateOrderResponse,
    OrderOut,
)

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


def to_stripe_amount(total: Decimal) -> int:
    """Convert a dollar Decimal to Stripe's integer cents without float math."""
    return int((total * 100).quantize(Decimal("1")))


def _client_secret_for(order: Order) -> str | None:
    """Look up the client secret again when a retried checkout replays an order."""
    settings = get_settings()
    if not (settings.STRIPE_SECRET_KEY and order.stripe_payment_intent_id):
        return None
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        intent = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)
    except stripe.error.StripeError as exc:
        log.error("stripe.payment_intent_retrieve_failed", error=str(exc))
        raise HTTPException(502, detail="payment provider error") from exc
    return intent.client_secret


@router.post(
    "",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order from the current cart",
)
async def create_order(
    payload: CreateOrderRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_KEY_PATTERN),
    ] = None,
) -> CreateOrderResponse:
    settings = get_settings()

    # Lock this user's cart row first. Concurrent checkouts by the same user
    # (double-clicks, retries, two tabs) now run one at a time, so the second
    # one sees the already-emptied cart or the order its key created.
    await db.execute(select(Cart.id).where(Cart.user_id == user.id).with_for_update())

    # Replayed request: return the order this key already created.
    if idempotency_key:
        existing = await db.scalar(
            select(Order)
            .where(Order.user_id == user.id, Order.idempotency_key == idempotency_key)
            .options(selectinload(Order.items))
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return CreateOrderResponse(
                order=_to_order_out(existing),
                payment_intent_client_secret=_client_secret_for(existing),
            )

    # Load cart with everything we need.
    cart = await db.scalar(
        select(Cart)
        .where(Cart.user_id == user.id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .execution_options(populate_existing=True)
    )
    if cart is None or not cart.items:
        raise HTTPException(400, detail="cart is empty")

    # Lock the product rows for the rest of this transaction so two checkouts
    # can't both buy the last unit. Locking in id order avoids deadlocks;
    # populate_existing refreshes stock/price to the locked values.
    product_ids = sorted({item.product_id for item in cart.items}, key=str)
    locked = {
        p.id: p
        for p in (
            await db.scalars(
                select(Product)
                .where(Product.id.in_(product_ids))
                .order_by(Product.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    }

    # Re-validate at order time: availability, stock and price can all have
    # changed since the item was added to the cart.
    price_changed = False
    for item in cart.items:
        product = locked.get(item.product_id)
        if product is None or not product.is_active:
            raise HTTPException(409, detail=f"product {item.product_id} is no longer available")
        if product.stock_quantity < item.quantity:
            raise HTTPException(409, detail=f"insufficient stock for {product.name}")
        if item.unit_price != product.price:
            item.unit_price = product.price
            price_changed = True
    if price_changed:
        # Update the cart to current prices and make the customer re-confirm,
        # rather than silently charging a different amount.
        await db.commit()
        raise HTTPException(409, detail="prices changed; please review your cart")

    subtotal = cart.subtotal
    tax = (subtotal * Decimal("0.0")).quantize(Decimal("0.01"))  # placeholder
    shipping = Decimal("0.00")  # placeholder — flat rate or carrier API in real life
    total = subtotal + tax + shipping
    if total <= 0:
        raise HTTPException(400, detail="order total must be positive")

    order = Order(
        user_id=user.id,
        order_number=_generate_order_number(),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        total=total,
        notes=payload.notes,
        idempotency_key=idempotency_key,
    )
    for cart_item in cart.items:
        product = locked[cart_item.product_id]
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                unit_price=cart_item.unit_price,
                quantity=cart_item.quantity,
            )
        )
        product.stock_quantity -= cart_item.quantity

    db.add(order)

    # Stripe payment intent (only if configured). The amount comes from the
    # server-side total, never from the client. Creating the intent before
    # commit means we avoid orphan orders if Stripe rejects.
    payment_intent_secret: str | None = None
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.create(
                amount=to_stripe_amount(total),
                currency="usd",
                automatic_payment_methods={"enabled": True},
                metadata={
                    "order_number": order.order_number,
                    "user_id": str(user.id),
                },
                idempotency_key=f"order-{order.order_number}",
            )
            order.stripe_payment_intent_id = intent.id
            payment_intent_secret = intent.client_secret
        except stripe.error.StripeError as exc:
            log.error("stripe.payment_intent_failed", error=str(exc))
            raise HTTPException(502, detail="payment provider error") from exc

    # Clear cart only after we're sure the order is going through.
    for cart_item in list(cart.items):
        await db.delete(cart_item)

    try:
        await db.commit()
    except IntegrityError as exc:
        # Backstop for the unique (user, Idempotency-Key) constraint.
        await db.rollback()
        raise HTTPException(409, detail="duplicate checkout request") from exc
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
