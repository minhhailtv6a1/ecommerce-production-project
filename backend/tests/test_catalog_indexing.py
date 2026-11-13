"""Unit tests for synchronous CLIP/Pinecone catalog synchronization."""

from typing import Any

import pytest

from app.services.catalog_indexing import (
    CatalogIndexer,
    CatalogIndexingError,
    DeferredCatalogIndexer,
)


class FakeEmbedder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.contents: list[bytes] = []

    def embed_image_bytes(self, content: bytes) -> list[float]:
        self.contents.append(content)
        if self.fail:
            raise RuntimeError("CLIP unavailable")
        return [0.25, 0.75]


class FakeDocuments:
    def __init__(self, *, accepted: int = 1, fail_delete: bool = False) -> None:
        self.accepted = accepted
        self.fail_delete = fail_delete
        self.upserts: list[list[dict[str, Any]]] = []
        self.updates: list[list[dict[str, Any]]] = []
        self.deletes: list[list[str]] = []

    def upsert(self, documents: list[dict[str, Any]]) -> int:
        self.upserts.append(documents)
        return self.accepted

    def update_fields(self, documents: list[dict[str, Any]]) -> None:
        self.updates.append(documents)

    def delete(self, ids: list[str]) -> None:
        if self.fail_delete:
            raise RuntimeError("Pinecone unavailable")
        self.deletes.append(list(ids))


def _indexer(
    *, accepted: int = 1, fail_embed: bool = False, fail_delete: bool = False
) -> tuple[CatalogIndexer, FakeEmbedder, FakeDocuments]:
    embedder = FakeEmbedder(fail=fail_embed)
    documents = FakeDocuments(accepted=accepted, fail_delete=fail_delete)
    return (
        CatalogIndexer(
            embedder=embedder,
            documents=documents,
            vector_field="image_vector",
        ),
        embedder,
        documents,
    )


def test_index_image_writes_search_contract_metadata() -> None:
    indexer, embedder, documents = _indexer()

    indexer.index_image(
        content=b"image",
        vector_id="admin-image-1",
        product_id="product-1",
        image_id="image-1",
        category_id="02",
        storage_path="catalog/admin/product-1/image.jpg",
    )

    assert embedder.contents == [b"image"]
    assert documents.upserts == [[{
        "_id": "admin-image-1",
        "image_vector": [0.25, 0.75],
        "category_id": "02",
        "image_path": "catalog/admin/product-1/image.jpg",
        "product_id": "product-1",
        "image_id": "image-1",
    }]]


def test_index_image_rejects_partial_pinecone_acceptance() -> None:
    indexer, _, _ = _indexer(accepted=0)

    with pytest.raises(CatalogIndexingError, match="accepted 0"):
        indexer.index_image(
            content=b"image",
            vector_id="vector-1",
            product_id="product-1",
            image_id="image-1",
            category_id="02",
            storage_path="catalog/image.jpg",
        )


def test_update_category_and_remove_are_noops_for_empty_ids() -> None:
    indexer, _, documents = _indexer()

    indexer.update_category(vector_ids=[], category_id="03")
    indexer.remove([])

    assert documents.updates == []
    assert documents.deletes == []


def test_remove_wraps_pinecone_failure() -> None:
    indexer, _, _ = _indexer(fail_delete=True)

    with pytest.raises(CatalogIndexingError, match="remove catalog vectors"):
        indexer.remove(["vector-1"])


def test_deferred_indexer_does_not_initialize_provider_for_empty_removal() -> None:
    calls = 0

    def provider() -> CatalogIndexer:
        nonlocal calls
        calls += 1
        return _indexer()[0]

    indexer = DeferredCatalogIndexer(provider)

    indexer.remove([])

    assert calls == 0
