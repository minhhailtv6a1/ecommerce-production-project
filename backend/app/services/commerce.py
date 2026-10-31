"""Cart and checkout business logic."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Protocol, Sequence
from uuid import UUID

from app.schemas.commerce import (
    CartItemResponse,
    CartResponse,
    CheckoutRequest,
    OrderItemResponse,
    OrderListResponse,
    OrderResponse,
)


class CartItemNotFoundError(RuntimeError):
    pass


class VariantUnavailableError(RuntimeError):
    pass


class InsufficientStockError(RuntimeError):
    pass


class CartQuantityLimitError(RuntimeError):
    pass


class OrderNotFoundError(RuntimeError):
    pass


class CommerceStore(Protocol):
    def list_cart_items(self, user_id: UUID) -> list[dict[str, Any]]: ...

    def get_variant(self, variant_id: UUID) -> dict[str, Any] | None: ...

    def set_cart_quantity(
        self, user_id: UUID, variant_id: UUID, quantity: int
    ) -> None: ...

    def delete_cart_item(self, user_id: UUID, variant_id: UUID) -> bool: ...

    def create_order_from_cart(self, **kwargs: Any) -> UUID: ...

    def list_orders(self, user_id: UUID) -> list[dict[str, Any]]: ...

    def get_order(self, user_id: UUID, order_id: UUID) -> dict[str, Any] | None: ...

    def get_order_items(self, order_ids: Sequence[UUID]) -> list[dict[str, Any]]: ...


class CommerceService:
    def __init__(self, store: CommerceStore) -> None:
        self.store = store

    def get_cart(self, user_id: UUID) -> CartResponse:
        rows = self.store.list_cart_items(user_id)
        items = [self._cart_item(row) for row in rows]
        currencies = {item.currency for item in items}
        return CartResponse(
            items=items,
            item_count=sum(item.quantity for item in items),
            subtotal=sum(item.line_total for item in items),
            currency=next(iter(currencies)) if len(currencies) == 1 else None,
        )

    def add_cart_item(
        self,
        user_id: UUID,
        variant_id: UUID,
        quantity: int,
    ) -> CartResponse:
        row = self._available_variant(variant_id)
        existing = next(
            (
                item
                for item in self.store.list_cart_items(user_id)
                if str(item["variant_id"]) == str(variant_id)
            ),
            None,
        )
        new_quantity = quantity + (int(existing["quantity"]) if existing else 0)
        if new_quantity > 99:
            raise CartQuantityLimitError
        self._ensure_stock(row, new_quantity)
        self.store.set_cart_quantity(user_id, variant_id, new_quantity)
        return self.get_cart(user_id)

    def update_cart_item(
        self,
        user_id: UUID,
        variant_id: UUID,
        quantity: int,
    ) -> CartResponse:
        existing = self.store.list_cart_items(user_id)
        if not any(str(row["variant_id"]) == str(variant_id) for row in existing):
            raise CartItemNotFoundError
        row = self._available_variant(variant_id)
        self._ensure_stock(row, quantity)
        self.store.set_cart_quantity(user_id, variant_id, quantity)
        return self.get_cart(user_id)

    def remove_cart_item(self, user_id: UUID, variant_id: UUID) -> None:
        if not self.store.delete_cart_item(user_id, variant_id):
            raise CartItemNotFoundError

    def checkout(self, user_id: UUID, request: CheckoutRequest) -> OrderResponse:
        order_id = self.store.create_order_from_cart(
            user_id=user_id,
            receiver_name=request.receiver_name,
            phone=request.phone,
            shipping_address=request.shipping_address,
            note=request.note,
        )
        return self.get_order(user_id, order_id)

    def list_orders(self, user_id: UUID) -> OrderListResponse:
        rows = self.store.list_orders(user_id)
        return OrderListResponse(items=self._hydrate_orders(rows))

    def get_order(self, user_id: UUID, order_id: UUID) -> OrderResponse:
        row = self.store.get_order(user_id, order_id)
        if row is None:
            raise OrderNotFoundError
        return self._hydrate_orders([row])[0]

    def _available_variant(self, variant_id: UUID) -> dict[str, Any]:
        row = self.store.get_variant(variant_id)
        if (
            row is None
            or not row["is_active"]
            or row["product_status"] != "published"
        ):
            raise VariantUnavailableError
        return row

    @staticmethod
    def _ensure_stock(row: dict[str, Any], quantity: int) -> None:
        if int(row["inventory_quantity"]) < quantity:
            raise InsufficientStockError

    @staticmethod
    def _cart_item(row: dict[str, Any]) -> CartItemResponse:
        quantity = int(row["quantity"])
        unit_price = int(row["unit_price"])
        available = (
            bool(row["is_active"])
            and row["product_status"] == "published"
            and int(row["inventory_quantity"]) >= quantity
        )
        return CartItemResponse(
            variant_id=row["variant_id"],
            product_id=row["product_id"],
            product_name=row["product_name"],
            product_slug=row["product_slug"],
            sku=row["sku"],
            color=row.get("color"),
            size=row.get("size"),
            unit_price=unit_price,
            currency=row["currency"],
            quantity=quantity,
            inventory_quantity=row["inventory_quantity"],
            available=available,
            line_total=unit_price * quantity,
        )

    def _hydrate_orders(self, rows: list[dict[str, Any]]) -> list[OrderResponse]:
        if not rows:
            return []
        order_ids = [row["id"] for row in rows]
        grouped: dict[str, list[OrderItemResponse]] = defaultdict(list)
        for item in self.store.get_order_items(order_ids):
            grouped[str(item["order_id"])].append(OrderItemResponse(**item))
        return [
            OrderResponse(**row, items=grouped[str(row["id"])]) for row in rows
        ]

