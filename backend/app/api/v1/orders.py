"""Order endpoints. Creating an order:
1. Validates the cart (non-empty, all items in stock at current quantities).
2. Snapshots prices/names into OrderItems and reserves stock.
3. Creates a Stripe Checkout Session (if Stripe is configured).
4. Clears the cart.

The order starts in PENDING. The signed Stripe webhook (`/payments/webhook`)
moves it to PAID, or to CANCELLED with stock returned if checkout expires.
See `app/services/payments.py` for the full flow.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import Role, User
from app.schemas.order import (
    CheckoutSessionResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    OrderOut,
    RefundRequest,
)
from app.services import payments

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
        paid_at=order.paid_at.isoformat() if order.paid_at else None,
        amount_refunded=order.amount_refunded or Decimal("0.00"),
        dispute_status=order.dispute_status,
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
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=255,
            description="Unique per checkout attempt. Retries with the same key "
            "return the original order instead of creating a second one.",
        ),
    ] = None,
) -> CreateOrderResponse:
    settings = get_settings()

    # A retry or double-click with the same key gets the first order back.
    if idempotency_key:
        existing = await _order_for_idempotency_key(db, user.id, idempotency_key)
        if existing is not None:
            return await _replay_created_order(existing, settings)

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
        id=uuid.uuid4(),  # known before flush: the Checkout Session references it
        user_id=user.id,
        order_number=_generate_order_number(),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        total=total,
        notes=payload.notes,
    )
    order.idempotency_key = idempotency_key
    # Reserve stock atomically: `stock = stock - n WHERE stock >= n` succeeds
    # for exactly as many buyers as there are units, even under concurrency.
    # A read-then-write check would let two buyers both take the last unit.
    # Products are reserved in id order so concurrent orders lock rows in the
    # same order and can't deadlock.
    for cart_item in sorted(cart.items, key=lambda i: str(i.product_id)):
        product = cart_item.product
        name = product.name
        reserved = await db.execute(
            update(Product)
            .where(
                Product.id == cart_item.product_id,
                Product.is_active.is_(True),
                Product.stock_quantity >= cart_item.quantity,
            )
            .values(stock_quantity=Product.stock_quantity - cart_item.quantity)
            .returning(Product.id)
            .execution_options(synchronize_session=False)
        )
        if reserved.scalar_one_or_none() is None:
            await db.rollback()
            raise HTTPException(409, detail=f"insufficient stock for {name}")
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=name,
                product_slug=product.slug,
                unit_price=cart_item.unit_price,
                quantity=cart_item.quantity,
            )
        )

    db.add(order)

    # Stripe Checkout Session (only if configured). Created before commit, so
    # if Stripe rejects the request nothing is saved and the cart is untouched.
    checkout_url: str | None = None
    if payments.payments_enabled(settings):
        try:
            session_id, checkout_url = await payments.create_checkout_session(
                settings, order, customer_email=user.email
            )
        except payments.PaymentError as exc:
            raise _payment_http_error(exc) from exc
        order.stripe_checkout_session_id = session_id

    # Clear cart only after we're sure the order is going through.
    for cart_item in list(cart.items):
        await db.delete(cart_item)

    try:
        await db.commit()
    except IntegrityError:
        # Two requests with the same Idempotency-Key raced; the other one won.
        # Our reservation is rolled back and we return the winner's order.
        await db.rollback()
        if idempotency_key:
            existing = await _order_for_idempotency_key(db, user.id, idempotency_key)
            if existing is not None:
                return await _replay_created_order(existing, settings)
        raise
    await db.refresh(order, ["items"])
    log.info("order.created", order_id=str(order.id), order_number=order.order_number)

    return CreateOrderResponse(order=_to_order_out(order), checkout_url=checkout_url)


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


async def _order_for_idempotency_key(
    db: AsyncSession, user_id: uuid.UUID, key: str
) -> Order | None:
    return await db.scalar(
        select(Order)
        .where(Order.user_id == user_id, Order.idempotency_key == key)
        .options(selectinload(Order.items))
    )


async def _replay_created_order(order: Order, settings) -> CreateOrderResponse:
    """Same response as the original request: the order, plus its payment page
    if it is still awaiting payment."""
    checkout_url: str | None = None
    if (
        order.status == OrderStatus.PENDING
        and order.stripe_checkout_session_id
        and payments.payments_enabled(settings)
    ):
        try:
            session = await payments.retrieve_checkout_session(
                settings, order.stripe_checkout_session_id
            )
            if payments.field(session, "status") == "open":
                checkout_url = payments.field(session, "url")
        except payments.PaymentError:
            checkout_url = None  # the order page's "Pay now" can recover this
    log.info("order.idempotent_replay", order_id=str(order.id))
    return CreateOrderResponse(order=_to_order_out(order), checkout_url=checkout_url)


def _payment_http_error(exc: payments.PaymentError) -> HTTPException:
    """503 + Retry-After when Stripe is down (nothing was saved, the cart is
    intact, try again soon); 502 when Stripe rejected the request."""
    if isinstance(exc, payments.PaymentUnavailableError):
        return HTTPException(
            503,
            detail=(
                "payments are temporarily unavailable; your cart is saved, please try again shortly"
            ),
            headers={"Retry-After": str(exc.retry_after)},
        )
    return HTTPException(502, detail="payment provider error")


async def _owned_order_for_payment(order_id: str, user: User, db: AsyncSession) -> Order:
    try:
        oid = uuid.UUID(order_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid order_id") from exc
    order = await payments.load_order_for_payment(db, oid)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order not found")
    return order


@router.post(
    "/{order_id}/checkout-session",
    response_model=CheckoutSessionResponse,
    summary="Get a Stripe payment page for a pending order (Pay now / retry)",
)
async def create_order_checkout_session(
    order_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutSessionResponse:
    settings = get_settings()
    if not payments.payments_enabled(settings):
        raise HTTPException(503, detail="payments are not configured")
    order = await _owned_order_for_payment(order_id, user, db)
    if order.status != OrderStatus.PENDING:
        raise HTTPException(409, detail=f"order is {order.status.value}, not awaiting payment")

    # One payment page per order: reuse the open one instead of creating a
    # second, so a customer can never pay twice for the same order.
    try:
        if order.stripe_checkout_session_id:
            current = await payments.retrieve_checkout_session(
                settings, order.stripe_checkout_session_id
            )
            outcome = await payments.apply_checkout_session(db, order, current, settings=settings)
            if outcome in {"paid", "cancelled"}:
                await db.commit()
                detail = (
                    "order is already paid"
                    if outcome == "paid"
                    else "checkout expired and the order was cancelled; its items were restocked"
                )
                raise HTTPException(409, detail=detail)
            url = payments.field(current, "url")
            if payments.field(current, "status") == "open" and url:
                return CheckoutSessionResponse(checkout_url=url)
            raise HTTPException(409, detail="a payment for this order is still processing")
        session_id, url = await payments.create_checkout_session(
            settings, order, customer_email=user.email, attempt=1
        )
    except payments.PaymentError as exc:
        raise _payment_http_error(exc) from exc

    order.stripe_checkout_session_id = session_id
    await db.commit()
    return CheckoutSessionResponse(checkout_url=url)


@router.post(
    "/{order_id}/sync-payment",
    response_model=OrderOut,
    summary="Re-check payment with Stripe (used after returning from checkout)",
)
async def sync_order_payment(
    order_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderOut:
    """The webhook is the source of truth, but it can arrive a few seconds after
    the customer is redirected back. This applies the same idempotent update
    from a direct Stripe lookup so the order page is correct immediately."""
    settings = get_settings()
    order = await _owned_order_for_payment(order_id, user, db)
    if (
        payments.payments_enabled(settings)
        and order.status == OrderStatus.PENDING
        and order.stripe_checkout_session_id
    ):
        try:
            session = await payments.retrieve_checkout_session(
                settings, order.stripe_checkout_session_id
            )
        except payments.PaymentError as exc:
            raise _payment_http_error(exc) from exc
        outcome = await payments.apply_checkout_session(db, order, session, settings=settings)
        if outcome in {"paid", "cancelled"}:
            await db.commit()
            await db.refresh(order, ["items"])
    return _to_order_out(order)


@router.post(
    "/{order_id}/refund",
    response_model=OrderOut,
    summary="Refund a paid order in full or in part (admin)",
)
async def refund_order(
    order_id: str,
    payload: RefundRequest,
    _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderOut:
    """Creates the refund in Stripe. The order's refunded amount is set from
    Stripe's answer now and kept authoritative by the `charge.refunded`
    webhook (which also covers refunds made in the Stripe dashboard)."""
    settings = get_settings()
    if not payments.payments_enabled(settings):
        raise HTTPException(503, detail="payments are not configured")
    try:
        oid = uuid.UUID(order_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid order_id") from exc
    order = await payments.load_order_for_payment(db, oid)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order not found")
    if order.status not in payments.REFUNDABLE or not order.stripe_payment_intent_id:
        raise HTTPException(409, detail=f"order is {order.status.value}; nothing to refund")

    remaining = order.total - order.amount_refunded
    amount = payload.amount if payload.amount is not None else remaining
    if amount <= 0 or amount > remaining:
        raise HTTPException(422, detail=f"refund must be between 0.01 and {remaining}")

    try:
        refund = await payments.create_refund(
            settings, order, amount_cents=payments.to_minor_units(amount), reason=payload.reason
        )
    except payments.PaymentError as exc:
        raise _payment_http_error(exc) from exc

    if payments.field(refund, "status") in {"succeeded", "pending"}:
        order.amount_refunded += amount
        if order.amount_refunded >= order.total:
            order.status = OrderStatus.REFUNDED
    await db.commit()
    await db.refresh(order, ["items"])
    log.info("order.refunded", order_id=str(order.id), amount=str(amount))
    return _to_order_out(order)
