"""Frontend-facing cart and order contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AddCartItemRequest(BaseModel):
    variant_id: UUID
    quantity: int = Field(default=1, ge=1, le=99)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartItemResponse(BaseModel):
    variant_id: UUID
    product_id: UUID
    product_name: str
    product_slug: str
    sku: str
    color: str | None = None
    size: str | None = None
    unit_price: int = Field(ge=0)
    currency: str
    quantity: int = Field(ge=1)
    inventory_quantity: int = Field(ge=0)
    available: bool
    line_total: int = Field(ge=0)


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    item_count: int = Field(ge=0)
    subtotal: int = Field(ge=0)
    currency: str | None = None


class CheckoutRequest(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=8, max_length=20)
    shipping_address: str = Field(min_length=5, max_length=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("receiver_name", "phone", "shipping_address")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("note")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


OrderStatus = Literal["pending", "confirmed", "shipping", "completed", "cancelled"]


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: UUID
    product_name: str
    sku: str
    color: str | None = None
    size: str | None = None
    unit_price: int = Field(ge=0)
    quantity: int = Field(ge=1)
    line_total: int = Field(ge=0)


class OrderResponse(BaseModel):
    id: UUID
    status: OrderStatus
    payment_method: Literal["cod"]
    receiver_name: str
    phone: str
    shipping_address: str
    note: str | None = None
    total_amount: int = Field(ge=0)
    currency: str
    created_at: datetime
    items: list[OrderItemResponse]


class OrderListResponse(BaseModel):
    items: list[OrderResponse]

