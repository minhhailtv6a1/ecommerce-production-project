"""Admin catalog business rules and external-system orchestration."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from math import ceil
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.repositories.admin_products import (
    AdminCatalogConflictError,
    AdminProductNotFoundError,
    AdminProductRepository,
)
from app.services.catalog_indexing import CatalogIndexer, CatalogIndexingError


logger = logging.getLogger(__name__)


class AdminProductNotPublishableError(RuntimeError):
    def __init__(self, reasons: Sequence[str]) -> None:
        super().__init__("Product is not publishable")
        self.reasons = tuple(reasons)


class AdminStorage(Protocol):
    def upload_bytes(
        self,
        *,
        storage_path: str,
        content: bytes,
        content_type: str,
        overwrite: bool = False,
    ) -> Any: ...

    def download(self, storage_path: str) -> bytes: ...


class ImageUrlResolver(Protocol):
    def resolve_many(self, storage_paths: Sequence[str]) -> dict[str, str]: ...


class AdminCatalogService:
    def __init__(
        self,
        *,
        products: AdminProductRepository,
        storage: AdminStorage,
        image_urls: ImageUrlResolver,
        indexer: CatalogIndexer,
    ) -> None:
        self.products = products
        self.storage = storage
        self.image_urls = image_urls
        self.indexer = indexer

    def list_products(self, **filters: Any) -> dict[str, Any]:
        rows, total = self.products.list_products(**filters)
        private_paths = tuple(
            str(row["primary_image_storage_path"])
            for row in rows
            if row.get("primary_image_storage_path") and not row.get("primary_image_public_url")
        )
        resolved = self.image_urls.resolve_many(private_paths) if private_paths else {}
        for row in rows:
            path = row.pop("primary_image_storage_path", None)
            public_url = row.pop("primary_image_public_url", None)
            row["primary_image_url"] = public_url or (resolved.get(str(path)) if path else None)
        page = int(filters["page"])
        page_size = int(filters["page_size"])
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0,
        }

    def get_product(self, product_id: UUID) -> dict[str, Any]:
        return self._decorate(self._require_product(product_id))

    def create_product(
        self,
        *,
        actor_id: UUID,
        values: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.products.category_is_active(str(values["category_id"])):
            raise AdminCatalogConflictError("Category is missing or inactive")
        try:
            product = self.products.create_product(actor_id=actor_id, values=values)
            self._audit(actor_id, "product.created", product["id"], None, product, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate(product)

    def update_product(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        expected_version: int,
        values: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        before = self._require_editable_product(product_id)
        category_id = values.get("category_id")
        if category_id is not None and not self.products.category_is_active(str(category_id)):
            raise AdminCatalogConflictError("Category is missing or inactive")
        try:
            updated = self.products.update_product(
                product_id=product_id,
                expected_version=expected_version,
                actor_id=actor_id,
                values=values,
            )
            if category_id is not None and category_id != before["category_id"]:
                self.indexer.update_category(
                    vector_ids=self._vector_ids(before),
                    category_id=str(category_id),
                )
            self._audit(actor_id, "product.updated", product_id, before, updated, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate(updated)

    def add_variant(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        values: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editable_product(product_id)
        try:
            variant = self.products.create_variant(product_id, values)
            self._audit(actor_id, "variant.created", variant["id"], None, variant, request_id)
            self.products.commit()
            return variant
        except Exception:
            self.products.rollback()
            raise

    def update_variant(
        self,
        *,
        product_id: UUID,
        variant_id: UUID,
        actor_id: UUID,
        values: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editable_product(product_id)
        try:
            variant = self.products.update_variant(product_id, variant_id, values)
            self._audit(actor_id, "variant.updated", variant_id, None, variant, request_id)
            self.products.commit()
            return variant
        except Exception:
            self.products.rollback()
            raise

    def deactivate_variant(
        self,
        *,
        product_id: UUID,
        variant_id: UUID,
        actor_id: UUID,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return self.update_variant(
            product_id=product_id,
            variant_id=variant_id,
            actor_id=actor_id,
            values={"is_active": False},
            request_id=request_id,
        )

    def upload_image(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        content: bytes,
        content_type: str,
        suffix: str,
        alt_text: str,
        sort_order: int,
        is_primary: bool,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        product = self._require_editable_product(product_id)
        if product["status"] == "published" and is_primary:
            raise AdminCatalogConflictError(
                "Archive and restore the product before replacing its primary image"
            )
        storage_path = f"catalog/admin/{product_id}/{uuid4().hex}{suffix}"
        upload = self.storage.upload_bytes(
            storage_path=storage_path,
            content=content,
            content_type=content_type,
            overwrite=False,
        )
        try:
            image = self.products.create_image(
                product_id=product_id,
                storage_path=storage_path,
                public_url=getattr(upload, "public_url", None),
                alt_text=alt_text,
                sort_order=sort_order,
                is_primary=is_primary,
            )
            self._audit(actor_id, "image.created", image["id"], None, image, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate_image(image)

    def update_image(
        self,
        *,
        product_id: UUID,
        image_id: UUID,
        actor_id: UUID,
        values: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        product = self._require_editable_product(product_id)
        current = next(
            (image for image in product["images"] if image["id"] == image_id),
            None,
        )
        if current is None:
            raise AdminProductNotFoundError
        if (
            product["status"] == "published"
            and values.get("is_primary") is True
            and not current["is_primary"]
        ):
            raise AdminCatalogConflictError(
                "Archive and restore the product before replacing its primary image"
            )
        try:
            image = self.products.update_image(product_id, image_id, values)
            self._audit(actor_id, "image.updated", image_id, None, image, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate_image(image)

    def remove_image(
        self,
        *,
        product_id: UUID,
        image_id: UUID,
        actor_id: UUID,
        request_id: str | None = None,
    ) -> None:
        self._require_editable_product(product_id)
        try:
            image = self.products.mark_image_removed(product_id, image_id)
            self.indexer.remove([image["pinecone_vector_id"]])
            self._audit(actor_id, "image.removed", image_id, image, None, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise

    def publish(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        product = self._require_product(product_id)
        reasons = self._publish_reasons(product)
        if not self.products.category_is_active(str(product["category_id"])):
            reasons.append("Product category is missing or inactive")
        if reasons:
            raise AdminProductNotPublishableError(reasons)
        primary = next(image for image in product["images"] if image["is_primary"])
        if product["status"] == "published" and primary["index_status"] == "indexed":
            return self._decorate(product)

        if primary["index_status"] != "indexed":
            self._index_primary(product)

        try:
            self.products.set_image_index_state(primary["id"], status="indexed")
            published = self.products.set_status(
                product_id=product_id,
                actor_id=actor_id,
                from_statuses=("draft", "published"),
                to_status="published",
            )
            self._audit(actor_id, "product.published", product_id, product, published, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate(published)

    def index_product(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        product = self._require_product(product_id)
        reasons: list[str] = []
        if product["status"] == "archived":
            reasons.append("Archived product must be restored before indexing")
        if not self.products.category_is_active(str(product["category_id"])):
            reasons.append("Product category is missing or inactive")
        primary = [image for image in product["images"] if image["is_primary"]]
        if len(primary) != 1:
            reasons.append("Exactly one primary image is required")
        if reasons:
            raise AdminProductNotPublishableError(reasons)
        if primary[0]["index_status"] != "indexed":
            self._index_primary(product)
        indexed = self._require_product(product_id)
        try:
            self._audit(actor_id, "product.indexed", product_id, product, indexed, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate(indexed)

    def _index_primary(self, product: Mapping[str, Any]) -> None:
        primary = next(image for image in product["images"] if image["is_primary"])
        product_id = UUID(str(product["id"]))
        self.products.set_image_index_state(primary["id"], status="indexing")
        self.products.commit()
        try:
            logger.info("Downloading primary image for product %s", product_id)
            content = self.storage.download(primary["storage_path"])
            logger.info("Embedding and indexing primary image for product %s", product_id)
            self.indexer.index_image(
                content=content,
                vector_id=primary["pinecone_vector_id"],
                product_id=str(product_id),
                image_id=str(primary["id"]),
                category_id=product["category_id"],
                storage_path=primary["storage_path"],
            )
            self.products.set_image_index_state(primary["id"], status="indexed")
            self.products.commit()
            logger.info("Catalog vector indexed for product %s", product_id)
        except Exception as exc:
            self.products.rollback()
            safe_error = f"{type(exc).__name__}: {exc}"[:1000]
            self.products.set_image_index_state(primary["id"], status="failed", error=safe_error)
            self.products.record_sync_failure(
                product_id=product_id,
                image_id=primary["id"],
                operation="upsert_vector",
                error=safe_error,
            )
            self.products.commit()
            raise CatalogIndexingError("Product indexing failed") from exc

    def archive(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        before = self._require_product(product_id)
        try:
            self.indexer.remove(self._vector_ids(before))
            self.products.mark_product_images_pending(product_id)
            archived = self.products.set_status(
                product_id=product_id,
                actor_id=actor_id,
                from_statuses=("draft", "published", "archived"),
                to_status="archived",
            )
            self._audit(actor_id, "product.archived", product_id, before, archived, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate(archived)

    def restore(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        before = self._require_product(product_id)
        try:
            restored = self.products.set_status(
                product_id=product_id,
                actor_id=actor_id,
                from_statuses=("archived", "draft"),
                to_status="draft",
            )
            self._audit(actor_id, "product.restored", product_id, before, restored, request_id)
            self.products.commit()
        except Exception:
            self.products.rollback()
            raise
        return self._decorate(restored)

    def _require_product(self, product_id: UUID) -> dict[str, Any]:
        product = self.products.get_product(product_id)
        if product is None:
            raise AdminProductNotFoundError
        return product

    def _require_editable_product(self, product_id: UUID) -> dict[str, Any]:
        product = self._require_product(product_id)
        if product["status"] == "archived":
            raise AdminCatalogConflictError(
                "Restore the archived product before editing it"
            )
        return product

    @staticmethod
    def _publish_reasons(product: Mapping[str, Any]) -> list[str]:
        reasons: list[str] = []
        if product["status"] == "archived":
            reasons.append("Archived product must be restored before publishing")
        if not str(product.get("name", "")).strip() or not str(product.get("slug", "")).strip():
            reasons.append("Product name and slug are required")
        if not any(variant["is_active"] for variant in product["variants"]):
            reasons.append("At least one active variant is required")
        primary = [image for image in product["images"] if image["is_primary"]]
        if len(primary) != 1:
            reasons.append("Exactly one primary image is required")
        return reasons

    @staticmethod
    def _vector_ids(product: Mapping[str, Any]) -> list[str]:
        return [
            str(image["pinecone_vector_id"])
            for image in product["images"]
            if image.get("index_status") in {"indexed", "indexing", "failed"}
        ]

    def _decorate(self, product: dict[str, Any]) -> dict[str, Any]:
        product = dict(product)
        product["images"] = [self._decorate_image(image) for image in product["images"]]
        return product

    def _decorate_image(self, image: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(image)
        path = str(result["storage_path"])
        if result.get("public_url"):
            result["url"] = result["public_url"]
        else:
            result["url"] = self.image_urls.resolve_many((path,)).get(path)
        return result

    def _audit(
        self,
        actor_id: UUID,
        action: str,
        resource_id: UUID,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
        request_id: str | None,
    ) -> None:
        self.products.record_audit(
            actor_id=actor_id,
            action=action,
            resource_type=action.split(".", 1)[0],
            resource_id=resource_id,
            before=_json_safe(before),
            after=_json_safe(after),
            request_id=request_id,
        )


def _json_safe(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(json.dumps(dict(value), default=str))
