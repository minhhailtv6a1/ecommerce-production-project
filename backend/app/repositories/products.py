"""PostgreSQL queries for public catalog products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence
from uuid import UUID


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
        if filters.sort == "newest":
            rows = self._list_newest_products(filters, where_sql, params)
        else:
            rows = self._list_products_by_price(filters, where_sql, params)
        if rows:
            total = int(rows[0].pop("_total"))
            for row in rows[1:]:
                row.pop("_total", None)
            return rows, total

        # Preserve the total for an out-of-range page without adding a second
        # round trip to the common successful-page path.
        count_row = self._fetchone(
            f"SELECT COUNT(*)::integer AS total FROM public.products p {where_sql}",
            params,
        )
        total = int(count_row["total"]) if count_row else 0
        return rows, total

    def _list_products_by_price(
        self,
        filters: ProductFilters,
        where_sql: str,
        params: list[Any],
    ) -> list[dict[str, Any]]:
        order_sql = {
            "price_asc": "price ASC, p.id",
            "price_desc": "price DESC, p.id",
        }[filters.sort]
        return self._fetchall(
            f"""
            SELECT p.id, p.slug, p.name, p.description, p.category_id,
                   p.brand, p.status, p.currency, p.created_at,
                   MIN(v.price)::bigint AS price,
                   MAX(v.compare_at_price)::bigint AS compare_at_price,
                   COALESCE(SUM(v.inventory_quantity), 0)::bigint AS inventory_quantity,
                   COUNT(*) OVER()::integer AS _total
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

    def _list_newest_products(
        self,
        filters: ProductFilters,
        where_sql: str,
        params: list[Any],
    ) -> list[dict[str, Any]]:
        """Page products before variant aggregation for the common newest sort."""
        return self._fetchall(
            f"""
            WITH product_page AS (
                SELECT p.id, COUNT(*) OVER()::integer AS total
                FROM public.products p
                {where_sql}
                ORDER BY p.created_at DESC, p.id
                LIMIT %s OFFSET %s
            )
            SELECT p.id, p.slug, p.name, p.description, p.category_id,
                   p.brand, p.status, p.currency, p.created_at,
                   MIN(v.price)::bigint AS price,
                   MAX(v.compare_at_price)::bigint AS compare_at_price,
                   COALESCE(SUM(v.inventory_quantity), 0)::bigint AS inventory_quantity,
                   page.total AS _total
            FROM product_page page
            JOIN public.products p ON p.id = page.id
            JOIN public.product_variants v
              ON v.product_id = p.id AND v.is_active = TRUE
            GROUP BY p.id, page.total
            ORDER BY p.created_at DESC, p.id
            """,
            [*params, filters.page_size, (filters.page - 1) * filters.page_size],
        )

    def get_product(self, identifier: str) -> dict[str, Any] | None:
        try:
            product_id = UUID(identifier)
        except ValueError:
            predicate = "p.slug = %s"
            value: str | UUID = identifier
        else:
            predicate = "p.id = %s"
            value = product_id
        return self._fetchone(
            f"""
            SELECT p.id, p.slug, p.name, p.description, p.category_id,
                   p.brand, p.status, p.currency, p.created_at,
                   MIN(v.price)::bigint AS price,
                   MAX(v.compare_at_price)::bigint AS compare_at_price,
                   COALESCE(SUM(v.inventory_quantity), 0)::bigint AS inventory_quantity
            FROM public.products p
            JOIN public.product_variants v
              ON v.product_id = p.id AND v.is_active = TRUE
            WHERE p.status = 'published'
              AND {predicate}
            GROUP BY p.id
            """,
            [value],
        )

    def get_products_by_ids(self, product_ids: Sequence[str]) -> list[dict[str, Any]]:
        ids = _valid_uuids(product_ids)
        if not ids:
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
            WHERE p.status = 'published' AND p.id = ANY(%s)
            GROUP BY p.id
            """,
            [ids],
        )

    def get_variants(self, product_ids: Sequence[str]) -> list[dict[str, Any]]:
        ids = _valid_uuids(product_ids)
        if not ids:
            return []
        return self._fetchall(
            """
            SELECT id, product_id, sku, color, size, price, compare_at_price,
                   inventory_quantity, is_active
            FROM public.product_variants
            WHERE product_id = ANY(%s) AND is_active = TRUE
            ORDER BY product_id, created_at, id
            """,
            [ids],
        )

    def get_images(self, product_ids: Sequence[str]) -> list[dict[str, Any]]:
        ids = _valid_uuids(product_ids)
        if not ids:
            return []
        return self._fetchall(
            """
            SELECT id, product_id, storage_path, public_url, alt_text,
                   sort_order, is_primary
            FROM public.product_images
            WHERE product_id = ANY(%s)
            ORDER BY product_id, is_primary DESC, sort_order, id
            """,
            [ids],
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


def _valid_uuids(values: Sequence[str]) -> list[UUID]:
    """Return valid, de-duplicated UUIDs while preserving input order."""
    result: list[UUID] = []
    seen: set[UUID] = set()
    for value in values:
        try:
            parsed = UUID(str(value))
        except ValueError:
            continue
        if parsed not in seen:
            seen.add(parsed)
            result.append(parsed)
    return result
