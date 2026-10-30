"""Tests for query-image selection and search orchestration."""

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

from app.repositories.pinecone import PineconeImageMatch
from app.services.image_search import (
    QueryImageError,
    discover_query_images,
    normalize_category_ids,
    search_similar_image_bytes,
    search_similar_images,
    select_query_image,
)


class FakeQueryEmbedder:
    def __init__(self) -> None:
        self.paths: list[Path] = []
        self.contents: list[bytes] = []

    def embed_image(self, path: Path) -> list[float]:
        self.paths.append(path)
        return [0.1, 0.2]

    def embed_image_bytes(self, content: bytes) -> list[float]:
        self.contents.append(content)
        return [0.1, 0.2]


class FakeSearcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def search_by_vector(
        self,
        *,
        vector: Sequence[float],
        vector_field: str,
        top_k: int,
        category_ids: Sequence[str] = (),
    ) -> tuple[PineconeImageMatch, ...]:
        self.calls.append(
            {
                "vector": list(vector),
                "vector_field": vector_field,
                "top_k": top_k,
                "category_ids": tuple(category_ids),
            }
        )
        return (
            PineconeImageMatch(
                id="00-id",
                score=0.9,
                category_id="00",
                image_path="00/product.jpg",
            ),
        )


def test_discover_query_images_supports_flat_and_nested_directories(
) -> None:
    root = Path("query-root")
    candidates = [
        root / "nested" / "a.png",
        root / "notes.txt",
        root / "b.JPG",
    ]
    with (
        patch.object(Path, "resolve", lambda self: self),
        patch.object(Path, "is_dir", lambda self: self == root),
        patch.object(Path, "is_file", lambda self: self != root),
        patch.object(Path, "rglob", return_value=candidates),
    ):
        images = discover_query_images(root)

    assert images == (
        root / "b.JPG",
        root / "nested" / "a.png",
    )


def test_random_query_selection_is_reproducible() -> None:
    root = Path("query-root")
    images = tuple(root / name for name in ("a.jpg", "b.jpg", "c.jpg"))
    with patch(
        "app.services.image_search.discover_query_images",
        return_value=images,
    ):
        first = select_query_image(root, randomize=True, seed=42)
        second = select_query_image(root, randomize=True, seed=42)

    assert first == second


def test_search_embeds_query_and_passes_category_filter() -> None:
    query_image = Path("query.jpg").resolve()
    embedder = FakeQueryEmbedder()
    searcher = FakeSearcher()

    with patch(
        "app.services.image_search.validate_query_image",
        return_value=query_image,
    ):
        matches = search_similar_images(
            query_image=query_image,
            embedder=embedder,
            searcher=searcher,
            vector_field="image_vector",
            top_k=5,
            category_ids=("00", "02", "00"),
        )

    assert embedder.paths == [query_image.resolve()]
    assert searcher.calls == [
        {
            "vector": [0.1, 0.2],
            "vector_field": "image_vector",
            "top_k": 5,
            "category_ids": ("00", "02"),
        }
    ]
    assert matches[0].image_path == "00/product.jpg"


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(QueryImageError, match="Unknown category IDs"):
        normalize_category_ids(("42",))


def test_uploaded_image_search_uses_same_vector_and_filter_contract() -> None:
    embedder = FakeQueryEmbedder()
    searcher = FakeSearcher()

    matches = search_similar_image_bytes(
        content=b"validated-image",
        embedder=embedder,
        searcher=searcher,
        vector_field="image_vector",
        top_k=3,
        category_ids=("00",),
    )

    assert embedder.contents == [b"validated-image"]
    assert searcher.calls[0]["top_k"] == 3
    assert searcher.calls[0]["category_ids"] == ("00",)
    assert matches[0].score == 0.9
