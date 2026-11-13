"""Business-rule tests for the admin catalog lifecycle."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.repositories.admin_products import AdminCatalogConflictError
from app.services.admin_catalog import (
    AdminCatalogService,
    AdminProductNotPublishableError,
)
from app.services.catalog_indexing import CatalogIndexingError


NOW = datetime.now(UTC)


def _product(*, valid: bool = True) -> dict[str, Any]:
    product_id = uuid4()
    return {
        "id": product_id,
        "slug": "ao-thun-test",
        "name": "Áo thun test",
        "description": None,
        "category_id": "02",
        "brand": "Test",
        "status": "draft",
        "currency": "VND",
        "version": 1,
        "created_by": None,
        "updated_by": None,
        "created_at": NOW,
        "updated_at": NOW,
        "variants": ([{
            "id": uuid4(),
            "sku": "SKU-1",
            "color": None,
            "size": None,
            "price": 100_000,
            "compare_at_price": None,
            "inventory_quantity": 3,
            "is_active": True,
            "created_at": NOW,
            "updated_at": NOW,
        }] if valid else []),
        "images": ([{
            "id": uuid4(),
            "pinecone_vector_id": "admin-vector-1",
            "storage_path": f"catalog/admin/{product_id}/primary.jpg",
            "public_url": None,
            "alt_text": "Ảnh chính",
            "sort_order": 0,
            "is_primary": True,
            "index_status": "pending",
            "indexed_at": None,
            "index_error": None,
            "created_at": NOW,
            "updated_at": NOW,
        }] if valid else []),
    }


class FakeRepository:
    def __init__(self, product: dict[str, Any]) -> None:
        self.product = product
        self.commits = 0
        self.rollbacks = 0
        self.audit_events: list[dict[str, Any]] = []
        self.sync_failures: list[dict[str, Any]] = []

    def get_product(self, product_id: UUID) -> dict[str, Any] | None:
        return deepcopy(self.product) if product_id == self.product["id"] else None

    def category_is_active(self, category_id: str) -> bool:
        return category_id == "02"

    def set_image_index_state(
        self, image_id: UUID, *, status: str, error: str | None = None
    ) -> None:
        image = next(item for item in self.product["images"] if item["id"] == image_id)
        image["index_status"] = status
        image["index_error"] = error
        image["indexed_at"] = NOW if status == "indexed" else None

    def set_status(
        self,
        *,
        product_id: UUID,
        actor_id: UUID,
        from_statuses: tuple[str, ...],
        to_status: str,
    ) -> dict[str, Any]:
        assert product_id == self.product["id"]
        assert self.product["status"] in from_statuses
        self.product["status"] = to_status
        self.product["updated_by"] = actor_id
        self.product["version"] += 1
        return deepcopy(self.product)

    def mark_product_images_pending(self, product_id: UUID) -> None:
        assert product_id == self.product["id"]
        for image in self.product["images"]:
            if image["index_status"] != "removed":
                image["index_status"] = "pending"
                image["index_error"] = None
                image["indexed_at"] = None

    def update_image(
        self, product_id: UUID, image_id: UUID, values: dict[str, Any]
    ) -> dict[str, Any]:
        assert product_id == self.product["id"]
        image = next(item for item in self.product["images"] if item["id"] == image_id)
        image.update(values)
        return deepcopy(image)

    def record_audit(self, **event: Any) -> None:
        self.audit_events.append(event)

    def record_sync_failure(self, **failure: Any) -> None:
        self.sync_failures.append(failure)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeStorage:
    def __init__(self) -> None:
        self.downloads: list[str] = []

    def upload_bytes(self, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(public_url=None)

    def download(self, storage_path: str) -> bytes:
        self.downloads.append(storage_path)
        return b"stored-image"


class FakeResolver:
    def resolve_many(self, paths: tuple[str, ...]) -> dict[str, str]:
        return {path: f"https://images.example/{path}" for path in paths}


class FakeIndexer:
    def __init__(self, *, fail_index: bool = False) -> None:
        self.fail_index = fail_index
        self.indexed: list[dict[str, Any]] = []
        self.removed: list[list[str]] = []

    def index_image(self, **document: Any) -> None:
        if self.fail_index:
            raise CatalogIndexingError("Pinecone unavailable")
        self.indexed.append(document)

    def remove(self, vector_ids: list[str]) -> None:
        self.removed.append(list(vector_ids))

    def update_category(self, **_: Any) -> None:
        return None


def _service(
    product: dict[str, Any], *, fail_index: bool = False
) -> tuple[AdminCatalogService, FakeRepository, FakeStorage, FakeIndexer]:
    repository = FakeRepository(product)
    storage = FakeStorage()
    indexer = FakeIndexer(fail_index=fail_index)
    service = AdminCatalogService(
        products=repository,  # type: ignore[arg-type]
        storage=storage,
        image_urls=FakeResolver(),
        indexer=indexer,  # type: ignore[arg-type]
    )
    return service, repository, storage, indexer


def test_publish_indexes_primary_image_before_making_product_public() -> None:
    product = _product()
    service, repository, storage, indexer = _service(product)
    actor_id = uuid4()

    result = service.publish(product_id=product["id"], actor_id=actor_id)

    assert result["status"] == "published"
    assert result["images"][0]["index_status"] == "indexed"
    assert result["images"][0]["url"].startswith("https://images.example/")
    assert storage.downloads == [product["images"][0]["storage_path"]]
    assert indexer.indexed == [{
        "content": b"stored-image",
        "vector_id": "admin-vector-1",
        "product_id": str(product["id"]),
        "image_id": str(product["images"][0]["id"]),
        "category_id": "02",
        "storage_path": product["images"][0]["storage_path"],
    }]
    assert repository.audit_events[-1]["action"] == "product.published"
    assert repository.commits == 3


def test_publish_rejects_product_without_variant_and_primary_image() -> None:
    product = _product(valid=False)
    service, repository, _, indexer = _service(product)

    with pytest.raises(AdminProductNotPublishableError) as error:
        service.publish(product_id=product["id"], actor_id=uuid4())

    assert "At least one active variant" in " ".join(error.value.reasons)
    assert "Exactly one primary image" in " ".join(error.value.reasons)
    assert repository.commits == 0
    assert indexer.indexed == []


def test_publish_revalidates_that_canonical_category_is_still_active() -> None:
    product = _product()
    product["category_id"] = "99"
    service, repository, _, indexer = _service(product)

    with pytest.raises(AdminProductNotPublishableError) as error:
        service.publish(product_id=product["id"], actor_id=uuid4())

    assert "category is missing or inactive" in " ".join(error.value.reasons)
    assert repository.commits == 0
    assert indexer.indexed == []


def test_index_failure_keeps_product_draft_and_records_retry_state() -> None:
    product = _product()
    service, repository, _, _ = _service(product, fail_index=True)

    with pytest.raises(CatalogIndexingError, match="indexing failed"):
        service.publish(product_id=product["id"], actor_id=uuid4())

    assert repository.product["status"] == "draft"
    assert repository.product["images"][0]["index_status"] == "failed"
    assert "CatalogIndexingError" in repository.product["images"][0]["index_error"]
    assert repository.sync_failures[0]["operation"] == "upsert_vector"
    assert repository.rollbacks == 1
    assert repository.commits == 2


def test_manual_index_does_not_publish_product() -> None:
    product = _product()
    service, repository, _, indexer = _service(product)

    result = service.index_product(product_id=product["id"], actor_id=uuid4())

    assert result["status"] == "draft"
    assert result["images"][0]["index_status"] == "indexed"
    assert len(indexer.indexed) == 1
    assert repository.audit_events[-1]["action"] == "product.indexed"


def test_archive_removes_vectors_and_restore_returns_to_draft() -> None:
    product = _product()
    product["status"] = "published"
    product["images"][0]["index_status"] = "indexed"
    service, repository, _, indexer = _service(product)
    actor_id = uuid4()

    archived = service.archive(product_id=product["id"], actor_id=actor_id)
    restored = service.restore(product_id=product["id"], actor_id=actor_id)

    assert archived["status"] == "archived"
    assert restored["status"] == "draft"
    assert restored["images"][0]["index_status"] == "pending"
    assert indexer.removed == [["admin-vector-1"]]
    assert [event["action"] for event in repository.audit_events] == [
        "product.archived",
        "product.restored",
    ]


def test_published_product_cannot_switch_to_an_unindexed_primary_image() -> None:
    product = _product()
    product["status"] = "published"
    product["images"][0]["index_status"] = "indexed"
    secondary = {**product["images"][0]}
    secondary.update({
        "id": uuid4(),
        "pinecone_vector_id": "admin-vector-2",
        "storage_path": f"catalog/admin/{product['id']}/secondary.jpg",
        "is_primary": False,
        "index_status": "pending",
    })
    product["images"].append(secondary)
    service, repository, _, _ = _service(product)

    with pytest.raises(AdminCatalogConflictError, match="Archive and restore"):
        service.update_image(
            product_id=product["id"],
            image_id=secondary["id"],
            actor_id=uuid4(),
            values={"is_primary": True},
        )

    assert repository.product["images"][0]["is_primary"] is True
    assert repository.product["images"][1]["is_primary"] is False


def test_archived_product_must_be_restored_before_editing() -> None:
    product = _product()
    product["status"] = "archived"
    service, _, _, _ = _service(product)

    with pytest.raises(AdminCatalogConflictError, match="Restore"):
        service.add_variant(
            product_id=product["id"],
            actor_id=uuid4(),
            values={"sku": "NEW", "price": 1000, "inventory_quantity": 1},
        )
