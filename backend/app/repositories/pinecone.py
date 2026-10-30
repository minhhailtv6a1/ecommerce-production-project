"""Pinecone SDK client construction and document data access."""

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any


class PineconeSdkUnavailableError(RuntimeError):
    """Raised when the supported Pinecone SDK cannot be imported."""


@dataclass(frozen=True)
class PineconeImageMatch:
    """One normalized image-search match returned by Pinecone."""

    id: str
    score: float
    category_id: str | None
    image_path: str | None
    product_id: str | None = None
    image_id: str | None = None


def create_pinecone_client(api_key: str) -> Any:
    """Create a Pinecone client without exposing the API key to logs."""
    try:
        from pinecone import Pinecone
    except Exception as exc:
        raise PineconeSdkUnavailableError(
            "The supported Pinecone SDK is unavailable. Install requirements.txt "
            "and remove the deprecated pinecone-client package if it is present."
        ) from exc

    return Pinecone(api_key=api_key)


class PineconeDocumentRepository:
    """Read and write image documents in one Pinecone namespace."""

    def __init__(self, index: Any, namespace: str) -> None:
        if not namespace.strip():
            raise ValueError("A non-empty Pinecone namespace is required")
        self._documents = index.documents
        self._namespace = namespace

    def upsert(self, documents: list[dict[str, Any]]) -> int:
        """Upsert one document batch and return the accepted record count."""
        if not documents:
            return 0
        response = self._documents.upsert(
            namespace=self._namespace,
            documents=documents,
        )
        return int(response.upserted_count)

    def update_fields(self, documents: list[dict[str, Any]]) -> None:
        """Partially update document fields without replacing vector values."""
        if not documents:
            return
        self._documents.update(
            namespace=self._namespace,
            documents=documents,
        )

    def fetch_fields(
        self,
        ids: Sequence[str],
        *,
        include_fields: Sequence[str],
    ) -> tuple[Any, ...]:
        """Fetch selected document fields for post-write verification."""
        if not ids:
            return ()
        response = self._documents.fetch(
            namespace=self._namespace,
            ids=list(ids),
            include_fields=list(include_fields),
        )
        documents = response.documents
        if isinstance(documents, Mapping):
            return tuple(documents.values())
        return tuple(documents)

    def search_by_vector(
        self,
        *,
        vector: Sequence[float],
        vector_field: str,
        top_k: int,
        category_ids: Sequence[str] = (),
    ) -> tuple[PineconeImageMatch, ...]:
        """Search by a caller-generated dense vector and optional categories."""
        try:
            from pinecone import DenseVectorQuery
        except Exception as exc:
            raise PineconeSdkUnavailableError(
                "Pinecone dense-vector search support is unavailable. "
                "Install requirements.txt."
            ) from exc

        metadata_filter = None
        if category_ids:
            metadata_filter = {"category_id": {"$in": list(category_ids)}}

        response = self._documents.search(
            namespace=self._namespace,
            score_by=[
                DenseVectorQuery(field=vector_field, values=list(vector))
            ],
            top_k=top_k,
            include_fields=[
                "category_id",
                "image_path",
                "product_id",
                "image_id",
            ],
            filter=metadata_filter,
        )
        return tuple(
            PineconeImageMatch(
                id=str(document.id),
                score=float(document.score),
                category_id=getattr(document, "category_id", None),
                image_path=getattr(document, "image_path", None),
                product_id=getattr(document, "product_id", None),
                image_id=getattr(document, "image_id", None),
            )
            for document in response.matches
        )
