"""Transactional PostgreSQL access for admin catalog management."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID, uuid4


class AdminCatalogRepositoryError(RuntimeError):
    """Raised when admin catalog persistence fails."""


class AdminProductNotFoundError(LookupError):
    """Raised when the requested product or child record does not exist."""


class AdminProductVersionConflictError(RuntimeError):
    """Raised when optimistic concurrency detects a stale product version."""


class AdminCatalogConflictError(RuntimeError):
    """Raised for slug, SKU, or other unique catalog conflicts."""


class AdminProductRepository:
    """Read and mutate draft/published/archived catalog state."""

    PRODUCT_UPDATE_FIELDS = frozenset(
        {"name", "slug", "description", "category_id", "brand", "currency"}
    )
    VARIANT_UPDATE_FIELDS = frozenset(
        {
            "sku", "color", "size", "price", "compare_at_price",
            "inventory_quantity", "is_active",
        }
    )
    IMAGE_UPDATE_FIELDS = frozenset({"alt_text", "sort_order", "is_primary"})

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def list_products(
        self,
        *,
        keyword: str | None,
        category_id: str | None,
        status: str | None,
        index_status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if keyword:
            conditions.append("(p.name ILIKE %s OR p.slug ILIKE %s OR p.brand ILIKE %s)")
            pattern = f"%{keyword}%"
            params.extend((pattern, pattern, pattern))
        if category_id:
            conditions.append("p.category_id = %s")
            params.append(category_id)
        if status:
            conditions.append("p.status = %s")
            params.append(status)
        if index_status:
            conditions.append(
                "EXISTS (SELECT 1 FROM public.product_images ix "
                "WHERE ix.product_id = p.id AND ix.index_status = %s)"
            )
            params.append(index_status)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._fetchall(
            f"""
            WITH filtered_products AS MATERIALIZED (
                SELECT p.* FROM public.products p {where}
            ), product_page AS (
                SELECT * FROM filtered_products
                ORDER BY updated_at DESC, id
                LIMIT %s OFFSET %s
            )
            SELECT p.id, p.slug, p.name, p.category_id, p.brand, p.status,
                   p.currency, p.version, p.updated_at,
                   MIN(v.price) FILTER (WHERE v.is_active)::bigint AS price_from,
                   COALESCE(SUM(v.inventory_quantity) FILTER (WHERE v.is_active), 0)::bigint
                       AS inventory_total,
                   primary_image.index_status,
                   primary_image.storage_path AS primary_image_storage_path,
                   primary_image.public_url AS primary_image_public_url,
                   primary_image.alt_text AS primary_image_alt,
                   (SELECT COUNT(*)::integer FROM filtered_products) AS _total
            FROM product_page p
            LEFT JOIN public.product_variants v ON v.product_id = p.id
            LEFT JOIN public.product_images primary_image
              ON primary_image.product_id = p.id
             AND primary_image.is_primary = TRUE
             AND primary_image.index_status <> 'removed'
            GROUP BY p.id, p.slug, p.name, p.category_id, p.brand, p.status,
                     p.currency, p.version, p.updated_at, primary_image.index_status,
                     primary_image.storage_path, primary_image.public_url,
                     primary_image.alt_text
            ORDER BY p.updated_at DESC, p.id
            """,
            [*params, page_size, (page - 1) * page_size],
        )
        total = int(rows[0].pop("_total")) if rows else 0
        for row in rows[1:]:
            row.pop("_total", None)
        if not rows and page > 1:
            count = self._fetchone(
                f"SELECT COUNT(*)::integer AS total FROM public.products p {where}",
                params,
            )
            total = int(count["total"]) if count else 0
        return rows, total

    def get_product(self, product_id: UUID) -> dict[str, Any] | None:
        product = self._fetchone(
            """
            SELECT id, slug, name, description, category_id, brand, status,
                   currency, version, created_by, updated_by, created_at, updated_at
            FROM public.products WHERE id = %s
            """,
            (product_id,),
        )
        if product is None:
            return None
        product["variants"] = self._fetchall(
            """
            SELECT id, sku, color, size, price, compare_at_price,
                   inventory_quantity, is_active, created_at, updated_at
            FROM public.product_variants
            WHERE product_id = %s ORDER BY created_at, id
            """,
            (product_id,),
        )
        product["images"] = self._fetchall(
            """
            SELECT id, pinecone_vector_id, storage_path, public_url, alt_text,
                   sort_order, is_primary, index_status, indexed_at, index_error,
                   created_at, updated_at
            FROM public.product_images
            WHERE product_id = %s AND index_status <> 'removed'
            ORDER BY is_primary DESC, sort_order, id
            """,
            (product_id,),
        )
        return product

    def category_is_active(self, category_id: str) -> bool:
        row = self._fetchone(
            "SELECT 1 AS found FROM public.categories WHERE id = %s AND is_active = TRUE",
            (category_id,),
        )
        return row is not None

    def create_product(
        self,
        *,
        actor_id: UUID,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        product_id = uuid4()
        try:
            row = self._fetchone(
                """
                INSERT INTO public.products (
                    id, slug, name, description, category_id, brand, status,
                    currency, created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s)
                RETURNING id
                """,
                (
                    product_id,
                    values["slug"], values["name"], values.get("description"),
                    values["category_id"], values.get("brand"), values["currency"],
                    actor_id, actor_id,
                ),
            )
        except Exception as exc:
            self._raise_conflict_or_repository(exc, "Unable to create product")
        if row is None:
            raise AdminCatalogRepositoryError("PostgreSQL did not return the product")
        return self._require_product(product_id)

    def update_product(
        self,
        *,
        product_id: UUID,
        expected_version: int,
        actor_id: UUID,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        updates = {key: value for key, value in values.items() if key in self.PRODUCT_UPDATE_FIELDS}
        if not updates:
            return self._require_product(product_id)
        assignments = [f"{field} = %s" for field in updates]
        params = [*updates.values(), actor_id, product_id, expected_version]
        try:
            row = self._fetchone(
                f"""
                UPDATE public.products
                SET {', '.join(assignments)}, updated_by = %s,
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND version = %s AND status <> 'archived'
                RETURNING id
                """,
                params,
            )
        except Exception as exc:
            self._raise_conflict_or_repository(exc, "Unable to update product")
        if row is None:
            self._raise_missing_or_version_conflict(product_id, expected_version)
        return self._require_product(product_id)

    def set_status(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        from_statuses: Sequence[str],
        to_status: str,
    ) -> dict[str, Any]:
        row = self._fetchone(
            """
            UPDATE public.products
            SET status = %s, updated_by = %s, version = version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = ANY(%s)
            RETURNING id
            """,
            (to_status, actor_id, product_id, list(from_statuses)),
        )
        if row is None:
            product = self.get_product(product_id)
            if product is None:
                raise AdminProductNotFoundError
            if product["status"] == to_status:
                return product
            raise AdminCatalogConflictError(
                f"Product cannot transition from {product['status']} to {to_status}"
            )
        return self._require_product(product_id)

    def create_variant(self, product_id: UUID, values: Mapping[str, Any]) -> dict[str, Any]:
        self._require_product(product_id)
        variant_id = uuid4()
        try:
            self._fetchone(
                """
                INSERT INTO public.product_variants (
                    id, product_id, sku, color, size, price, compare_at_price,
                    inventory_quantity, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    variant_id, product_id, values["sku"], values.get("color"),
                    values.get("size"), values["price"], values.get("compare_at_price"),
                    values["inventory_quantity"], values["is_active"],
                ),
            )
        except Exception as exc:
            self._raise_conflict_or_repository(exc, "Unable to create variant")
        return self._require_variant(product_id, variant_id)

    def update_variant(
        self,
        product_id: UUID,
        variant_id: UUID,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        updates = {key: value for key, value in values.items() if key in self.VARIANT_UPDATE_FIELDS}
        assignments = [f"{field} = %s" for field in updates]
        try:
            row = self._fetchone(
                f"""
                UPDATE public.product_variants
                SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND product_id = %s RETURNING id
                """,
                [*updates.values(), variant_id, product_id],
            )
        except Exception as exc:
            self._raise_conflict_or_repository(exc, "Unable to update variant")
        if row is None:
            raise AdminProductNotFoundError
        return self._require_variant(product_id, variant_id)

    def deactivate_variant(self, product_id: UUID, variant_id: UUID) -> dict[str, Any]:
        return self.update_variant(product_id, variant_id, {"is_active": False})

    def create_image(
        self,
        *,
        product_id: UUID,
        storage_path: str,
        public_url: str | None,
        alt_text: str,
        sort_order: int,
        is_primary: bool,
    ) -> dict[str, Any]:
        self._require_product(product_id)
        image_id = uuid4()
        if is_primary:
            self._execute(
                "UPDATE public.product_images SET is_primary = FALSE, updated_at = CURRENT_TIMESTAMP "
                "WHERE product_id = %s AND is_primary = TRUE",
                (product_id,),
            )
        row = self._fetchone(
            """
            INSERT INTO public.product_images (
                id, product_id, pinecone_vector_id, source_path, storage_path,
                public_url, alt_text, sort_order, is_primary, index_status
            ) VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, 'pending')
            RETURNING id
            """,
            (
                image_id, product_id, f"admin-{image_id}", storage_path,
                public_url, alt_text, sort_order, is_primary,
            ),
        )
        if row is None:
            raise AdminCatalogRepositoryError("PostgreSQL did not return the image")
        return self._require_image(product_id, image_id)

    def update_image(
        self,
        product_id: UUID,
        image_id: UUID,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        current = self._require_image(product_id, image_id)
        if current["is_primary"] and values.get("is_primary") is False:
            raise AdminCatalogConflictError("Choose another primary image first")
        if values.get("is_primary") is True:
            self._execute(
                "UPDATE public.product_images SET is_primary = FALSE, updated_at = CURRENT_TIMESTAMP "
                "WHERE product_id = %s AND id <> %s AND is_primary = TRUE",
                (product_id, image_id),
            )
        updates = {key: value for key, value in values.items() if key in self.IMAGE_UPDATE_FIELDS}
        assignments = [f"{field} = %s" for field in updates]
        row = self._fetchone(
            f"""
            UPDATE public.product_images
            SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND product_id = %s AND index_status <> 'removed'
            RETURNING id
            """,
            [*updates.values(), image_id, product_id],
        )
        if row is None:
            raise AdminProductNotFoundError
        return self._require_image(product_id, image_id)

    def mark_image_removed(self, product_id: UUID, image_id: UUID) -> dict[str, Any]:
        image = self._require_image(product_id, image_id)
        if image["is_primary"]:
            raise AdminCatalogConflictError("Choose another primary image before deleting")
        self._execute(
            """
            UPDATE public.product_images
            SET index_status = 'removed', indexed_at = NULL, index_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND product_id = %s
            """,
            (image_id, product_id),
        )
        return image

    def set_image_index_state(
        self,
        image_id: UUID,
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        self._execute(
            """
            UPDATE public.product_images
            SET index_status = %s,
                indexed_at = CASE WHEN %s = 'indexed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                index_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, status, error, image_id),
        )

    def mark_product_images_pending(self, product_id: UUID) -> None:
        self._execute(
            """
            UPDATE public.product_images
            SET index_status = 'pending', indexed_at = NULL, index_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE product_id = %s AND index_status <> 'removed'
            """,
            (product_id,),
        )

    def record_audit(
        self,
        *,
        actor_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
        request_id: str | None = None,
    ) -> None:
        from psycopg.types.json import Jsonb

        self._execute(
            """
            INSERT INTO public.admin_audit_events (
                id, actor_user_id, action, resource_type, resource_id,
                before_data, after_data, request_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(), actor_id, action, resource_type, resource_id,
                Jsonb(dict(before)) if before is not None else None,
                Jsonb(dict(after)) if after is not None else None,
                request_id,
            ),
        )

    def record_sync_failure(
        self,
        *,
        product_id: UUID,
        image_id: UUID | None,
        operation: str,
        error: str,
    ) -> None:
        self._execute(
            """
            INSERT INTO public.catalog_sync_jobs (
                id, product_id, image_id, operation, status, attempts, last_error
            ) VALUES (%s, %s, %s, %s, 'failed', 1, %s)
            """,
            (uuid4(), product_id, image_id, operation, error[:1000]),
        )

    def _require_product(self, product_id: UUID) -> dict[str, Any]:
        product = self.get_product(product_id)
        if product is None:
            raise AdminProductNotFoundError
        return product

    def _require_variant(self, product_id: UUID, variant_id: UUID) -> dict[str, Any]:
        row = self._fetchone(
            """
            SELECT id, sku, color, size, price, compare_at_price,
                   inventory_quantity, is_active, created_at, updated_at
            FROM public.product_variants WHERE id = %s AND product_id = %s
            """,
            (variant_id, product_id),
        )
        if row is None:
            raise AdminProductNotFoundError
        return row

    def _require_image(self, product_id: UUID, image_id: UUID) -> dict[str, Any]:
        row = self._fetchone(
            """
            SELECT id, pinecone_vector_id, storage_path, public_url, alt_text,
                   sort_order, is_primary, index_status, indexed_at, index_error,
                   created_at, updated_at
            FROM public.product_images
            WHERE id = %s AND product_id = %s AND index_status <> 'removed'
            """,
            (image_id, product_id),
        )
        if row is None:
            raise AdminProductNotFoundError
        return row

    def _raise_missing_or_version_conflict(self, product_id: UUID, expected: int) -> None:
        row = self._fetchone(
            "SELECT version FROM public.products WHERE id = %s",
            (product_id,),
        )
        if row is None:
            raise AdminProductNotFoundError
        raise AdminProductVersionConflictError(
            f"Product version is {row['version']}, expected {expected}"
        )

    @staticmethod
    def _raise_conflict_or_repository(exc: Exception, message: str) -> None:
        if getattr(exc, "sqlstate", None) in {"23505", "23503", "23514"}:
            raise AdminCatalogConflictError(message) from exc
        raise AdminCatalogRepositoryError(message) from exc

    def _fetchone(
        self,
        statement: str,
        parameters: Sequence[Any] = (),
    ) -> dict[str, Any] | None:
        from psycopg.rows import dict_row

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(statement, parameters)
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def _fetchall(
        self,
        statement: str,
        parameters: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        from psycopg.rows import dict_row

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(statement, parameters)
            return [dict(row) for row in cursor.fetchall()]

    def _execute(self, statement: str, parameters: Sequence[Any] = ()) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(statement, parameters)
