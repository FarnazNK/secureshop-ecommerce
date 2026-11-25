"""Cart + order schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

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
    paid_at: str | None = None
    amount_refunded: Decimal = Decimal("0.00")
    dispute_status: str | None = None

    model_config = {"from_attributes": True}


class CreateOrderRequest(BaseModel):
    """Convert the current cart into an order. When Stripe is configured, a
    Checkout Session is created server-side and its URL is returned."""

    notes: str | None = Field(default=None, max_length=1000)


class CreateOrderResponse(BaseModel):
    order: OrderOut
    # Stripe-hosted payment page. The storefront redirects here; None when
    # payments are not configured (demo mode).
    checkout_url: str | None = None


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class RefundRequest(BaseModel):
    # Omit for a full refund of whatever has not been refunded yet.
    amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    reason: Literal["duplicate", "fraudulent", "requested_by_customer"] | None = None


class PaymentConfigOut(BaseModel):
    enabled: bool
    test_mode: bool
    currency: str
