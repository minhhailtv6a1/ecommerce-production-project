"""Synchronous CLIP/Pinecone lifecycle for admin-managed product images."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, Sequence


class CatalogIndexingError(RuntimeError):
    """Raised when a catalog vector cannot be synchronized."""


class ByteImageEmbedder(Protocol):
    def embed_image_bytes(self, content: bytes) -> list[float]: ...


class CatalogDocumentRepository(Protocol):
    def upsert(self, documents: list[dict[str, Any]]) -> int: ...

    def delete(self, ids: Sequence[str]) -> None: ...

    def update_fields(self, documents: list[dict[str, Any]]) -> None: ...


class CatalogIndexer:
    def __init__(
        self,
        *,
        embedder: ByteImageEmbedder,
        documents: CatalogDocumentRepository,
        vector_field: str,
    ) -> None:
        self._embedder = embedder
        self._documents = documents
        self._vector_field = vector_field

    def index_image(
        self,
        *,
        content: bytes,
        vector_id: str,
        product_id: str,
        image_id: str,
        category_id: str,
        storage_path: str,
    ) -> None:
        try:
            vector = self._embedder.embed_image_bytes(content)
            accepted = self._documents.upsert(
                [
                    {
                        "_id": vector_id,
                        self._vector_field: vector,
                        "category_id": category_id,
                        "image_path": storage_path,
                        "product_id": product_id,
                        "image_id": image_id,
                    }
                ]
            )
        except Exception as exc:
            raise CatalogIndexingError("Unable to index the product image") from exc
        if accepted != 1:
            raise CatalogIndexingError(
                f"Pinecone accepted {accepted} documents instead of 1"
            )

    def update_category(self, *, vector_ids: Sequence[str], category_id: str) -> None:
        if not vector_ids:
            return
        try:
            self._documents.update_fields(
                [{"_id": vector_id, "category_id": category_id} for vector_id in vector_ids]
            )
        except Exception as exc:
            raise CatalogIndexingError("Unable to update vector category metadata") from exc

    def remove(self, vector_ids: Sequence[str]) -> None:
        if not vector_ids:
            return
        try:
            self._documents.delete(vector_ids)
        except Exception as exc:
            raise CatalogIndexingError("Unable to remove catalog vectors") from exc


class DeferredCatalogIndexer:
    """Avoid initializing CLIP/Pinecone for admin reads and draft-only writes."""

    def __init__(self, provider: Callable[[], CatalogIndexer]) -> None:
        self._provider = provider

    def index_image(self, **values: Any) -> None:
        self._provider().index_image(**values)

    def update_category(self, *, vector_ids: Sequence[str], category_id: str) -> None:
        if vector_ids:
            self._provider().update_category(
                vector_ids=vector_ids,
                category_id=category_id,
            )

    def remove(self, vector_ids: Sequence[str]) -> None:
        if vector_ids:
            self._provider().remove(vector_ids)
