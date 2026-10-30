"""PostgreSQL queries for public catalog products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence


ProductSort = Literal["newest", "price_asc", "price_desc"]


@dataclass(frozen=True)
class ProductFilters:
    category_ids: tuple[str, ...] = ()
    size: str | None = None
    color: str | None = None
    brand: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    in_stock: bool | None = None
    sort: ProductSort = "newest"
    page: int = 1
    page_size: int = 20


class ProductRepository:
    """Read the authoritative public product catalog from PostgreSQL."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def list_categories(self) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT c.id, c.slug, c.name, c.description,
                   COUNT(p.id)::integer AS product_count
            FROM public.categories c
            LEFT JOIN public.products p
              ON p.category_id = c.id AND p.status = 'published'
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.slug, c.name, c.description, c.display_order
            ORDER BY c.display_order, c.id
            """
        )

    def list_products(
        self,
        filters: ProductFilters,
    ) -> tuple[list[dict[str, Any]], int]:
        where_sql, params = self._product_where(filters)
        count_row = self._fetchone(
            f"SELECT COUNT(*)::integer AS total FROM public.products p {where_sql}",
            params,
        )
        total = int(count_row["total"]) if count_row else 0
        if not total:
            return [], 0

        order_sql = {
            "newest": "p.created_at DESC, p.id",
            "price_asc": "price ASC, p.id",
            "price_desc": "price DESC, p.id",
        }[filters.sort]
        rows = self._fetchall(
            f"""
            SELECT p.id, p.slug, p.name, p.description, p.category_id,
                   p.brand, p.status, p.currency, p.created_at,
                   MIN(v.price)::bigint AS price,
                   MAX(v.compare_at_price)::bigint AS compare_at_price,
                   COALESCE(SUM(v.inventory_quantity), 0)::bigint AS inventory_quantity
            FROM public.products p
            JOIN public.product_variants v
              ON v.product_id = p.id AND v.is_active = TRUE
            {where_sql}
            GROUP BY p.id
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
            """,
            [*params, filters.page_size, (filters.page - 1) * filters.page_size],
        )
        return rows, total

    def get_product(self, identifier: str) -> dict[str, Any] | None:
        return self._fetchone(
            """
            SELECT p.id, p.slug, p.name, p.description, p.category_id,
                   p.brand, p.status, p.currency, p.created_at,
                   MIN(v.price)::bigint AS price,
                   MAX(v.compare_at_price)::bigint AS compare_at_price,
                   COALESCE(SUM(v.inventory_quantity), 0)::bigint AS inventory_quantity
            FROM public.products p
            JOIN public.product_variants v
              ON v.product_id = p.id AND v.is_active = TRUE
            WHERE p.status = 'published'
              AND (p.id::text = %s OR p.slug = %s)
            GROUP BY p.id
            """,
            [identifier, identifier],
        )

    def get_products_by_ids(self, product_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        return self._fetchall(
            """
            SELECT p.id, p.slug, p.name, p.description, p.category_id,
                   p.brand, p.status, p.currency, p.created_at,
                   MIN(v.price)::bigint AS price,
                   MAX(v.compare_at_price)::bigint AS compare_at_price,
                   COALESCE(SUM(v.inventory_quantity), 0)::bigint AS inventory_quantity
            FROM public.products p
            JOIN public.product_variants v
              ON v.product_id = p.id AND v.is_active = TRUE
            WHERE p.status = 'published' AND p.id::text = ANY(%s)
            GROUP BY p.id
            """,
            [list(product_ids)],
        )

    def get_variants(self, product_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        return self._fetchall(
            """
            SELECT id, product_id, sku, color, size, price, compare_at_price,
                   inventory_quantity, is_active
            FROM public.product_variants
            WHERE product_id::text = ANY(%s) AND is_active = TRUE
            ORDER BY product_id, created_at, id
            """,
            [list(product_ids)],
        )

    def get_images(self, product_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        return self._fetchall(
            """
            SELECT id, product_id, storage_path, public_url, alt_text,
                   sort_order, is_primary
            FROM public.product_images
            WHERE product_id::text = ANY(%s)
            ORDER BY product_id, is_primary DESC, sort_order, id
            """,
            [list(product_ids)],
        )

    def _product_where(self, filters: ProductFilters) -> tuple[str, list[Any]]:
        conditions = ["p.status = 'published'"]
        params: list[Any] = []
        if filters.category_ids:
            conditions.append("p.category_id = ANY(%s)")
            params.append(list(filters.category_ids))
        if filters.brand:
            conditions.append("p.brand = %s")
            params.append(filters.brand)

        variant_conditions = ["fv.product_id = p.id", "fv.is_active = TRUE"]
        if filters.size:
            variant_conditions.append("fv.size = %s")
            params.append(filters.size)
        if filters.color:
            variant_conditions.append("fv.color = %s")
            params.append(filters.color)
        if filters.min_price is not None:
            variant_conditions.append("fv.price >= %s")
            params.append(filters.min_price)
        if filters.max_price is not None:
            variant_conditions.append("fv.price <= %s")
            params.append(filters.max_price)
        if filters.in_stock is True:
            variant_conditions.append("fv.inventory_quantity > 0")
        elif filters.in_stock is False:
            variant_conditions.append("fv.inventory_quantity = 0")
        conditions.append(
            "EXISTS (SELECT 1 FROM public.product_variants fv WHERE "
            + " AND ".join(variant_conditions)
            + ")"
        )
        return "WHERE " + " AND ".join(conditions), params

    def _fetchall(
        self,
        sql: str,
        params: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        from psycopg.rows import dict_row

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def _fetchone(
        self,
        sql: str,
        params: Sequence[Any] = (),
    ) -> dict[str, Any] | None:
        from psycopg.rows import dict_row

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()
