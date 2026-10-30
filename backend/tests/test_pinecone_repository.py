"""Tests for Pinecone document data access."""

from types import SimpleNamespace
from typing import Any

from app.repositories.pinecone import PineconeDocumentRepository


class FakeDocumentsApi:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def upsert(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(upserted_count=len(kwargs["documents"]))

    def search(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            matches=[
                SimpleNamespace(
                    id="00-stable-id",
                    score=0.91,
                    category_id="00",
                    image_path="00/product.jpg",
                    product_id="product-1",
                    image_id="image-1",
                )
            ]
        )

    def update(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace()

    def fetch(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            documents=[
                SimpleNamespace(
                    id="00-stable-id",
                    product_id="product-1",
                    image_id="image-1",
                )
            ]
        )


def test_document_repository_uses_documents_api_and_namespace() -> None:
    documents_api = FakeDocumentsApi()
    index = SimpleNamespace(documents=documents_api)
    repository = PineconeDocumentRepository(index, "image-vector-search")
    documents = [
        {
            "_id": "00-stable-id",
            "image_vector": [0.5, 0.5],
            "category_id": "00",
            "image_path": "00/product.jpg",
        }
    ]

    accepted = repository.upsert(documents)

    assert accepted == 1
    assert documents_api.calls == [
        {
            "namespace": "image-vector-search",
            "documents": documents,
        }
    ]


def test_document_repository_searches_vector_with_category_filter() -> None:
    documents_api = FakeDocumentsApi()
    index = SimpleNamespace(documents=documents_api)
    repository = PineconeDocumentRepository(index, "image-vector-search")

    matches = repository.search_by_vector(
        vector=[0.1, 0.2],
        vector_field="image_vector",
        top_k=5,
        category_ids=("00", "02"),
    )

    call = documents_api.calls[0]
    scoring_method = call["score_by"][0]
    assert call["namespace"] == "image-vector-search"
    assert scoring_method.field == "image_vector"
    assert scoring_method.values == [0.1, 0.2]
    assert call["top_k"] == 5
    assert call["include_fields"] == [
        "category_id",
        "image_path",
        "product_id",
        "image_id",
    ]
    assert call["filter"] == {"category_id": {"$in": ["00", "02"]}}
    assert matches[0].id == "00-stable-id"
    assert matches[0].score == 0.91
    assert matches[0].category_id == "00"
    assert matches[0].image_path == "00/product.jpg"
    assert matches[0].product_id == "product-1"
    assert matches[0].image_id == "image-1"


def test_document_repository_partially_updates_and_fetches_fields() -> None:
    documents_api = FakeDocumentsApi()
    repository = PineconeDocumentRepository(
        SimpleNamespace(documents=documents_api),
        "image-vector-search",
    )
    patches = [
        {
            "_id": "00-stable-id",
            "product_id": "product-1",
            "image_id": "image-1",
        }
    ]

    repository.update_fields(patches)
    fetched = repository.fetch_fields(
        ["00-stable-id"],
        include_fields=("product_id", "image_id"),
    )

    assert documents_api.calls == [
        {
            "namespace": "image-vector-search",
            "documents": patches,
        },
        {
            "namespace": "image-vector-search",
            "ids": ["00-stable-id"],
            "include_fields": ["product_id", "image_id"],
        },
    ]
    assert fetched[0].product_id == "product-1"
