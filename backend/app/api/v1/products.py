"""Product catalog endpoints. List + detail are public; create/update/delete
require admin role."""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_role
from app.db.session import get_db
from app.models.product import Product
from app.models.user import Role, User
from app.schemas.common import PageMeta
from app.schemas.product import (
    ProductCreate,
    ProductOut,
    ProductPage,
    ProductUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=ProductPage,
    summary="List products with pagination and filters",
)
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1, le=10_000),
    limit: int = Query(default=20, ge=1, le=100),
    category_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    is_featured: bool | None = Query(default=None),
) -> ProductPage:
    """Public product listing. All filters optional."""
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True))
        .options(selectinload(Product.images), selectinload(Product.category))
    )

    if category_id:
        try:
            stmt = stmt.where(Product.category_id == uuid.UUID(category_id))
        except ValueError as exc:
            raise HTTPException(400, detail="invalid category_id") from exc

    if search:
        # Simple ILIKE — for real prod, use Postgres full-text search (tsvector).
        pattern = f"%{search}%"
        stmt = stmt.where(Product.name.ilike(pattern))

    if is_featured is not None:
        stmt = stmt.where(Product.is_featured.is_(is_featured))

    # Count first, then paginate. Two queries but each is cheap with the
    # right indexes, and gives us total_pages without loading everything.
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * limit
    stmt = stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    products = (await db.execute(stmt)).scalars().all()

    total_pages = max(1, math.ceil(total / limit))
    return ProductPage(
        items=[ProductOut.model_validate(p) for p in products],
        meta=PageMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    try:
        pid = uuid.UUID(product_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid product_id") from exc

    stmt = (
        select(Product)
        .where(Product.id == pid, Product.is_active.is_(True))
        .options(selectinload(Product.images), selectinload(Product.category))
    )
    product = await db.scalar(stmt)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    return ProductOut.model_validate(product)


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product (admin only)",
)
async def create_product(
    payload: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> ProductOut:
    product = Product(**payload.model_dump(exclude={"category_id"}))
    if payload.category_id:
        product.category_id = uuid.UUID(payload.category_id)
    db.add(product)
    await db.commit()
    await db.refresh(product, ["images", "category"])
    return ProductOut.model_validate(product)


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Update a product (admin only)",
)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> ProductOut:
    try:
        pid = uuid.UUID(product_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid product_id") from exc

    product = await db.get(Product, pid)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")

    updates = payload.model_dump(exclude_unset=True, exclude={"category_id"})
    for key, value in updates.items():
        setattr(product, key, value)
    if payload.category_id is not None:
        product.category_id = uuid.UUID(payload.category_id) if payload.category_id else None

    await db.commit()
    await db.refresh(product, ["images", "category"])
    return ProductOut.model_validate(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product (admin only)",
)
async def delete_product(
    product_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> None:
    try:
        pid = uuid.UUID(product_id)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid product_id") from exc
    product = await db.get(Product, pid)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    # Soft delete via is_active=False would be safer for audit; we use hard
    # delete here to keep the demo simple.
    await db.delete(product)
    await db.commit()
