"""Order endpoints. Creating an order happens in one database transaction:

1. Claims the request's ``Idempotency-Key`` (if sent). A retry of a request that already
   succeeded returns the original order instead of placing a second one.
2. Reserves stock with an atomic conditional UPDATE per product, so two checkouts can never
   both take the last unit.
3. Snapshots prices/names into OrderItems.
4. Creates a Stripe payment intent with its own idempotency key (if Stripe is configured).
5. Clears the cart.

Any failure rolls back all of it, including the idempotency claim, so the client can retry.
The order starts in PENDING; the Stripe webhook (``payments.py``) moves it to PAID or
CANCELLED.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC
from decimal import Decimal
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.money import to_cents
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import IdempotencyKey
from app.models.product import Product
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


IdempotencyKeyHeader = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=255,
        description=(
            "Client-generated unique key (e.g. a UUID) for this checkout attempt. "
            "Retrying with the same key returns the original order instead of placing a new one."
        ),
    ),
]


@router.post(
    "",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order from the current cart",
    responses={
        200: {"description": "Replay: this Idempotency-Key already created an order"},
        409: {"description": "Insufficient stock or product unavailable"},
        422: {"description": "Idempotency-Key reused with a different request body"},
    },
)
async def create_order(
    payload: CreateOrderRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKeyHeader = None,
) -> CreateOrderResponse:
    settings = get_settings()

    claim: IdempotencyKey | None = None
    if idempotency_key is not None:
        request_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        # If another transaction holds the same key, Postgres makes this INSERT wait until
        # that transaction commits or rolls back, so we never see a half-finished request.
        claimed_id = await db.scalar(
            pg_insert(IdempotencyKey)
            .values(
                id=uuid.uuid4(), user_id=user.id, key=idempotency_key, request_hash=request_hash
            )
            .on_conflict_do_nothing(constraint="uq_idempotency_key_user_key")
            .returning(IdempotencyKey.id)
        )
        if claimed_id is None:
            return await _replay(db, user, idempotency_key, request_hash, response)
        claim = await db.get(IdempotencyKey, claimed_id)

    # Load cart with everything we need.
    cart = await db.scalar(
        select(Cart)
        .where(Cart.user_id == user.id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    if cart is None or not cart.items:
        raise HTTPException(400, detail="cart is empty")
    for item in cart.items:
        if item.product is None or not item.product.is_active:
            raise HTTPException(409, detail=f"product {item.product_id} is no longer available")

    # Reserve stock atomically. Each UPDATE succeeds only if enough stock remains, and the
    # row lock it takes makes concurrent checkouts of the same product queue up instead of
    # both reading the old quantity. Products are locked in id order so two carts with the
    # same products can't deadlock.
    for item in sorted(cart.items, key=lambda cart_item: cart_item.product_id):
        remaining = await db.scalar(
            update(Product)
            .where(Product.id == item.product_id, Product.stock_quantity >= item.quantity)
            .values(stock_quantity=Product.stock_quantity - item.quantity)
            .returning(Product.stock_quantity)
            .execution_options(synchronize_session=False)
        )
        if remaining is None:
            raise HTTPException(409, detail=f"insufficient stock for {item.product.name}")

    subtotal = cart.subtotal
    tax = (subtotal * Decimal("0.0")).quantize(Decimal("0.01"))  # placeholder
    shipping = Decimal("0.00")  # placeholder — flat rate or carrier API in real life
    total = subtotal + tax + shipping

    order = Order(
        id=uuid.uuid4(),
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
    db.add(order)

    payment_intent_secret: str | None = None
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            # The Stripe SDK is synchronous; run it in a worker thread so a slow call to
            # Stripe doesn't block the event loop for every other request.
            intent = await run_in_threadpool(
                stripe.PaymentIntent.create,
                amount=to_cents(total),
                currency="usd",
                metadata={"order_number": order.order_number, "user_id": str(user.id)},
                # If this transaction rolls back after Stripe succeeded, the client's retry
                # (same Idempotency-Key) gets the same payment intent back, not a second one.
                idempotency_key=(
                    f"checkout:{user.id}:{idempotency_key}"
                    if idempotency_key
                    else f"order:{order.id}"
                ),
            )
            order.stripe_payment_intent_id = intent.id
            payment_intent_secret = intent.client_secret
        except stripe.error.StripeError as exc:
            log.error("stripe.payment_intent_failed", error=str(exc))
            raise HTTPException(502, detail="payment provider error") from exc

    # Clear cart only after we're sure the order is going through.
    for cart_item in list(cart.items):
        await db.delete(cart_item)

    if claim is not None:
        claim.order_id = order.id

    await db.commit()
    await db.refresh(order, ["items"])
    log.info("order.created", order_id=str(order.id), order_number=order.order_number)

    return CreateOrderResponse(
        order=_to_order_out(order),
        payment_intent_client_secret=payment_intent_secret,
    )


async def _replay(
    db: AsyncSession, user: User, key: str, request_hash: str, response: Response
) -> CreateOrderResponse:
    """Answer a retried checkout with the order its first request created."""
    claim = await db.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == user.id, IdempotencyKey.key == key)
    )
    if claim is None or claim.order_id is None:
        # The claim and its order are written in one transaction, so this only happens if
        # the order was deleted since. Treat the key as spent.
        raise HTTPException(409, detail="idempotency key already used")
    if claim.request_hash != request_hash:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="idempotency key was already used with a different request body",
        )
    order = await db.scalar(
        select(Order).where(Order.id == claim.order_id).options(selectinload(Order.items))
    )
    if order is None:
        raise HTTPException(409, detail="idempotency key already used")

    secret: str | None = None
    settings = get_settings()
    if settings.STRIPE_SECRET_KEY and order.stripe_payment_intent_id:
        # Not stored in our database; fetch it again so the client can still pay.
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = await run_in_threadpool(
                stripe.PaymentIntent.retrieve, order.stripe_payment_intent_id
            )
            secret = intent.client_secret
        except stripe.error.StripeError as exc:
            log.error("stripe.payment_intent_retrieve_failed", error=str(exc))
            raise HTTPException(502, detail="payment provider error") from exc

    response.status_code = status.HTTP_200_OK
    response.headers["Idempotent-Replayed"] = "true"
    log.info("order.replayed", order_id=str(order.id))
    return CreateOrderResponse(order=_to_order_out(order), payment_intent_client_secret=secret)


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
