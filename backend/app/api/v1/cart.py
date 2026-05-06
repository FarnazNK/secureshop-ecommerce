"""Cart endpoints. All require authentication — guest carts live on the client.

The cart is created lazily on first add (one cart per user, enforced by a
unique constraint on cart.user_id).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    AddToCartRequest,
    CartItemOut,
    CartOut,
    UpdateCartItemRequest,
)
from app.schemas.product import ProductOut

router = APIRouter()


async def _get_or_create_cart(db: AsyncSession, user: User) -> Cart:
    """Return the user's cart, creating one if it doesn't exist."""
    cart = await db.scalar(
        select(Cart)
        .where(Cart.user_id == user.id)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.images)
        )
    )
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    return cart


def _serialize_cart(cart: Cart) -> CartOut:
    """Build the API response from the loaded cart aggregate."""
    return CartOut(
        id=str(cart.id),
        items=[
            CartItemOut(
                id=str(item.id),
                product_id=str(item.product_id),
                product=ProductOut.model_validate(item.product),
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in cart.items
        ],
        subtotal=cart.subtotal,
        item_count=cart.item_count,
    )


@router.get("", response_model=CartOut)
async def get_cart(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    cart = await _get_or_create_cart(db, user)
    return _serialize_cart(cart)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    payload: AddToCartRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    """Add a product to the cart, or bump quantity if it's already there."""
    try:
        product_id = uuid.UUID(payload.product_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid product_id") from exc

    product = await db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(404, detail="product not found")

    if product.stock_quantity < payload.quantity:
        raise HTTPException(409, detail="insufficient stock")

    cart = await _get_or_create_cart(db, user)
    existing = next((i for i in cart.items if i.product_id == product_id), None)
    if existing is not None:
        new_qty = existing.quantity + payload.quantity
        if new_qty > product.stock_quantity:
            raise HTTPException(409, detail="insufficient stock")
        existing.quantity = new_qty
    else:
        cart.items.append(
            CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=payload.quantity,
                unit_price=product.price,
            )
        )
    await db.commit()
    # Reload to get fresh aggregate including new product images.
    await db.refresh(cart)
    cart = await _get_or_create_cart(db, user)
    return _serialize_cart(cart)


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_cart_item(
    item_id: str,
    payload: UpdateCartItemRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    try:
        iid = uuid.UUID(item_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid item_id") from exc

    item = await db.scalar(
        select(CartItem).where(CartItem.id == iid).options(selectinload(CartItem.cart))
    )
    if item is None or item.cart.user_id != user.id:
        raise HTTPException(404, detail="cart item not found")

    product = await db.get(Product, item.product_id)
    if product is not None and product.stock_quantity < payload.quantity:
        raise HTTPException(409, detail="insufficient stock")

    item.quantity = payload.quantity
    await db.commit()
    cart = await _get_or_create_cart(db, user)
    return _serialize_cart(cart)


@router.delete("/items/{item_id}", response_model=CartOut)
async def remove_cart_item(
    item_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    try:
        iid = uuid.UUID(item_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid item_id") from exc

    item = await db.scalar(
        select(CartItem).where(CartItem.id == iid).options(selectinload(CartItem.cart))
    )
    if item is None or item.cart.user_id != user.id:
        raise HTTPException(404, detail="cart item not found")

    await db.delete(item)
    await db.commit()
    cart = await _get_or_create_cart(db, user)
    return _serialize_cart(cart)


@router.delete("", response_model=CartOut)
async def clear_cart(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    cart = await _get_or_create_cart(db, user)
    for item in list(cart.items):
        await db.delete(item)
    await db.commit()
    cart = await _get_or_create_cart(db, user)
    return _serialize_cart(cart)
