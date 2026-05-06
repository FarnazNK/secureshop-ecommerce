"""Product / category schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import Page


class CategoryRef(BaseModel):
    """Lightweight category reference for embedding in product responses."""

    id: str
    name: str
    slug: str

    model_config = {"from_attributes": True}


class ProductImageOut(BaseModel):
    url: str
    alt: str | None = None
    position: int

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    """Product as returned by the API (list and detail use the same shape)."""

    id: str
    name: str
    slug: str
    short_description: str | None = None
    description: str | None = None
    price: Decimal
    compare_at_price: Decimal | None = None
    stock_quantity: int
    is_active: bool
    is_featured: bool
    images: list[ProductImageOut] = Field(default_factory=list)
    category: CategoryRef | None = None

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    """Admin-only: create a new product."""

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=280, pattern=r"^[a-z0-9-]+$")
    short_description: str | None = None
    description: str | None = None
    price: Decimal = Field(ge=Decimal("0.01"))
    compare_at_price: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    is_featured: bool = False
    category_id: str | None = None


class ProductUpdate(BaseModel):
    """Admin-only: partial update."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    short_description: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    compare_at_price: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_featured: bool | None = None
    category_id: str | None = None


# Page[ProductOut] is the response type for GET /products.
ProductPage = Page[ProductOut]
