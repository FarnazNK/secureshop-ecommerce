"""Cart + order schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.order import OrderStatus
from app.schemas.product import ProductOut

# --- Cart ---


class CartItemOut(BaseModel):
    id: str
    product_id: str
    product: ProductOut
    quantity: int
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class CartOut(BaseModel):
    id: str
    items: list[CartItemOut]
    subtotal: Decimal
    item_count: int

    model_config = {"from_attributes": True}


class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=999)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=999)


# --- Orders ---


class OrderItemOut(BaseModel):
    id: str
    product_id: str | None
    product_name: str
    product_slug: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: str
    order_number: str
    status: OrderStatus
    subtotal: Decimal
    tax: Decimal
    shipping: Decimal
    total: Decimal
    items: list[OrderItemOut]
    notes: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class CreateOrderRequest(BaseModel):
    """Convert the current cart into an order. Stripe payment intent is
    created server-side and its client secret is returned."""

    notes: str | None = Field(default=None, max_length=1000)


class CreateOrderResponse(BaseModel):
    order: OrderOut
    # Stripe client secret for the payment intent. Frontend uses this with
    # Stripe Elements to confirm the payment.
    payment_intent_client_secret: str | None = None
