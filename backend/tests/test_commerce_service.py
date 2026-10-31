"""Unit tests for cart and order business logic."""

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

import pytest

from app.schemas.commerce import CheckoutRequest
from app.services.commerce import (
    CartItemNotFoundError,
    CartQuantityLimitError,
    CommerceService,
    InsufficientStockError,
    OrderNotFoundError,
)


class FakeCommerceStore:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.product_id = uuid4()
        self.variant_id = uuid4()
        self.order_id = uuid4()
        self.quantity: int | None = None
        self.variant = {
            "variant_id": self.variant_id,
            "product_id": self.product_id,
            "product_name": "Áo thun demo",
            "product_slug": "ao-thun-demo",
            "product_status": "published",
            "currency": "VND",
            "sku": "SKU-01",
            "color": "Đen",
            "size": "M",
            "unit_price": 100_000,
            "inventory_quantity": 10,
            "is_active": True,
        }
        self.order = {
            "id": self.order_id,
            "status": "pending",
            "payment_method": "cod",
            "receiver_name": "Nguyen Van A",
            "phone": "0900000000",
            "shipping_address": "1 Nguyen Hue, TP HCM",
            "note": None,
            "total_amount": 200_000,
            "currency": "VND",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }

    def list_cart_items(self, user_id: UUID) -> list[dict[str, Any]]:
        if self.quantity is None:
            return []
        return [{**self.variant, "quantity": self.quantity}]

    def get_variant(self, variant_id: UUID) -> dict[str, Any] | None:
        return self.variant if variant_id == self.variant_id else None

    def set_cart_quantity(self, user_id: UUID, variant_id: UUID, quantity: int) -> None:
        self.quantity = quantity

    def delete_cart_item(self, user_id: UUID, variant_id: UUID) -> bool:
        if self.quantity is None or variant_id != self.variant_id:
            return False
        self.quantity = None
        return True

    def create_order_from_cart(self, **kwargs: Any) -> UUID:
        self.quantity = None
        return self.order_id

    def list_orders(self, user_id: UUID) -> list[dict[str, Any]]:
        return [self.order]

    def get_order(self, user_id: UUID, order_id: UUID) -> dict[str, Any] | None:
        return self.order if order_id == self.order_id else None

    def get_order_items(self, order_ids: Sequence[UUID]) -> list[dict[str, Any]]:
        if self.order_id not in order_ids:
            return []
        return [
            {
                "id": uuid4(),
                "order_id": self.order_id,
                "product_id": self.product_id,
                "variant_id": self.variant_id,
                "product_name": self.variant["product_name"],
                "sku": self.variant["sku"],
                "color": self.variant["color"],
                "size": self.variant["size"],
                "unit_price": 100_000,
                "quantity": 2,
                "line_total": 200_000,
            }
        ]


def test_add_cart_item_accumulates_and_calculates_totals() -> None:
    store = FakeCommerceStore()
    service = CommerceService(store)

    first = service.add_cart_item(store.user_id, store.variant_id, 2)
    second = service.add_cart_item(store.user_id, store.variant_id, 3)

    assert first.item_count == 2
    assert second.item_count == 5
    assert second.subtotal == 500_000
    assert second.items[0].available is True


def test_cart_rejects_stock_and_quantity_limit() -> None:
    store = FakeCommerceStore()
    service = CommerceService(store)

    with pytest.raises(InsufficientStockError):
        service.add_cart_item(store.user_id, store.variant_id, 11)

    store.variant["inventory_quantity"] = 200
    store.quantity = 98
    with pytest.raises(CartQuantityLimitError):
        service.add_cart_item(store.user_id, store.variant_id, 2)


def test_update_and_remove_require_existing_cart_item() -> None:
    store = FakeCommerceStore()
    service = CommerceService(store)

    with pytest.raises(CartItemNotFoundError):
        service.update_cart_item(store.user_id, store.variant_id, 1)
    with pytest.raises(CartItemNotFoundError):
        service.remove_cart_item(store.user_id, store.variant_id)


def test_checkout_and_order_reads_return_snapshotted_items() -> None:
    store = FakeCommerceStore()
    store.quantity = 2
    service = CommerceService(store)

    order = service.checkout(
        store.user_id,
        CheckoutRequest(
            receiver_name=" Nguyen Van A ",
            phone="0900000000",
            shipping_address="1 Nguyen Hue, TP HCM",
        ),
    )

    assert order.id == store.order_id
    assert order.payment_method == "cod"
    assert order.items[0].line_total == 200_000
    assert store.quantity is None
    assert service.list_orders(store.user_id).items[0].id == store.order_id
    with pytest.raises(OrderNotFoundError):
        service.get_order(store.user_id, uuid4())

