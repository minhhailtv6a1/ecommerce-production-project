"""PostgreSQL persistence for carts and orders."""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID, uuid4


class CommerceRepositoryError(RuntimeError):
    """Raised when cart or order persistence fails unexpectedly."""


class EmptyCartError(RuntimeError):
    """Raised when checkout is attempted with an empty cart."""


class CartItemUnavailableError(RuntimeError):
    """Raised when a cart item can no longer be purchased."""


class MixedCurrencyCartError(RuntimeError):
    """Raised when one order would contain multiple currencies."""


class CommerceRepository:
    """Store one authenticated user's cart and immutable order snapshots."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def list_cart_items(self, user_id: UUID) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT v.id AS variant_id, p.id AS product_id, p.name AS product_name,
                   p.slug AS product_slug, p.status AS product_status, p.currency,
                   v.sku, v.color, v.size, v.price AS unit_price,
                   v.inventory_quantity, v.is_active, ci.quantity
            FROM public.cart_items ci
            JOIN public.product_variants v ON v.id = ci.variant_id
            JOIN public.products p ON p.id = v.product_id
            WHERE ci.user_id = %s
            ORDER BY ci.created_at, v.id
            """,
            (user_id,),
        )

    def get_variant(self, variant_id: UUID) -> dict[str, Any] | None:
        return self._fetchone(
            """
            SELECT v.id AS variant_id, p.id AS product_id, p.name AS product_name,
                   p.slug AS product_slug, p.status AS product_status, p.currency,
                   v.sku, v.color, v.size, v.price AS unit_price,
                   v.inventory_quantity, v.is_active
            FROM public.product_variants v
            JOIN public.products p ON p.id = v.product_id
            WHERE v.id = %s
            """,
            (variant_id,),
        )

    def set_cart_quantity(
        self,
        user_id: UUID,
        variant_id: UUID,
        quantity: int,
    ) -> None:
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.cart_items (user_id, variant_id, quantity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, variant_id) DO UPDATE
                    SET quantity = EXCLUDED.quantity,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, variant_id, quantity),
                )
            self.connection.commit()
        except Exception as exc:
            self.connection.rollback()
            raise CommerceRepositoryError("Unable to update cart") from exc

    def delete_cart_item(self, user_id: UUID, variant_id: UUID) -> bool:
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM public.cart_items
                    WHERE user_id = %s AND variant_id = %s
                    """,
                    (user_id, variant_id),
                )
                deleted = cursor.rowcount > 0
            self.connection.commit()
            return deleted
        except Exception as exc:
            self.connection.rollback()
            raise CommerceRepositoryError("Unable to remove cart item") from exc

    def create_order_from_cart(
        self,
        *,
        user_id: UUID,
        receiver_name: str,
        phone: str,
        shipping_address: str,
        note: str | None,
    ) -> UUID:
        """Atomically validate the cart, reserve stock, and create an order."""
        order_id = uuid4()
        try:
            items = self._fetchall(
                """
                SELECT ci.quantity, v.id AS variant_id, v.product_id, v.sku,
                       v.color, v.size, v.price AS unit_price,
                       v.inventory_quantity, v.is_active, p.name AS product_name,
                       p.status AS product_status, p.currency
                FROM public.cart_items ci
                JOIN public.product_variants v ON v.id = ci.variant_id
                JOIN public.products p ON p.id = v.product_id
                WHERE ci.user_id = %s
                ORDER BY v.id
                FOR UPDATE OF ci, v
                """,
                (user_id,),
            )
            if not items:
                raise EmptyCartError
            if any(
                not row["is_active"]
                or row["product_status"] != "published"
                or row["inventory_quantity"] < row["quantity"]
                for row in items
            ):
                raise CartItemUnavailableError

            currencies = {str(row["currency"]) for row in items}
            if len(currencies) != 1:
                raise MixedCurrencyCartError
            currency = currencies.pop()
            total_amount = sum(
                int(row["unit_price"]) * int(row["quantity"]) for row in items
            )

            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.orders (
                        id, user_id, status, payment_method, receiver_name, phone,
                        shipping_address, note, total_amount, currency
                    ) VALUES (%s, %s, 'pending', 'cod', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        user_id,
                        receiver_name,
                        phone,
                        shipping_address,
                        note,
                        total_amount,
                        currency,
                    ),
                )
                for row in items:
                    quantity = int(row["quantity"])
                    unit_price = int(row["unit_price"])
                    cursor.execute(
                        """
                        INSERT INTO public.order_items (
                            id, order_id, product_id, variant_id, product_name,
                            sku, color, size, unit_price, quantity, line_total
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            uuid4(),
                            order_id,
                            row["product_id"],
                            row["variant_id"],
                            row["product_name"],
                            row["sku"],
                            row["color"],
                            row["size"],
                            unit_price,
                            quantity,
                            unit_price * quantity,
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE public.product_variants
                        SET inventory_quantity = inventory_quantity - %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (quantity, row["variant_id"]),
                    )
                cursor.execute(
                    "DELETE FROM public.cart_items WHERE user_id = %s",
                    (user_id,),
                )
            self.connection.commit()
            return order_id
        except (EmptyCartError, CartItemUnavailableError, MixedCurrencyCartError):
            self.connection.rollback()
            raise
        except Exception as exc:
            self.connection.rollback()
            raise CommerceRepositoryError("Unable to create order") from exc

    def list_orders(self, user_id: UUID) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT id, status, payment_method, receiver_name, phone,
                   shipping_address, note, total_amount, currency, created_at
            FROM public.orders
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        )

    def get_order(self, user_id: UUID, order_id: UUID) -> dict[str, Any] | None:
        return self._fetchone(
            """
            SELECT id, status, payment_method, receiver_name, phone,
                   shipping_address, note, total_amount, currency, created_at
            FROM public.orders
            WHERE user_id = %s AND id = %s
            """,
            (user_id, order_id),
        )

    def get_order_items(self, order_ids: Sequence[UUID]) -> list[dict[str, Any]]:
        if not order_ids:
            return []
        return self._fetchall(
            """
            SELECT id, order_id, product_id, variant_id, product_name, sku,
                   color, size, unit_price, quantity, line_total
            FROM public.order_items
            WHERE order_id = ANY(%s)
            ORDER BY order_id, id
            """,
            (list(order_ids),),
        )

    def _fetchall(
        self,
        sql: str,
        params: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        try:
            from psycopg.rows import dict_row

            with self.connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
        except Exception as exc:
            raise CommerceRepositoryError("Unable to read commerce data") from exc

    def _fetchone(
        self,
        sql: str,
        params: Sequence[Any] = (),
    ) -> dict[str, Any] | None:
        try:
            from psycopg.rows import dict_row

            with self.connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        except Exception as exc:
            raise CommerceRepositoryError("Unable to read commerce data") from exc

