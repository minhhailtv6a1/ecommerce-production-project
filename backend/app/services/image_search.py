"""Query-image selection and vector-search orchestration."""

from __future__ import annotations

import random
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from app.repositories.pinecone import PineconeImageMatch
from app.services.image_ingestion import (
    CANONICAL_CATEGORY_IDS,
    SUPPORTED_IMAGE_EXTENSIONS,
)


class QueryImageError(ValueError):
    """Raised when a query image or search option is invalid."""


class QueryImageEmbedder(Protocol):
    """Embedding interface needed by query-image search."""

    def embed_image(self, path: Path) -> list[float]: ...


class UploadedImageEmbedder(Protocol):
    """Embedding interface for validated encoded upload bytes."""

    def embed_image_bytes(self, content: bytes) -> list[float]: ...


class ImageVectorSearcher(Protocol):
    """Dense-vector search interface needed by the service."""

    def search_by_vector(
        self,
        *,
        vector: Sequence[float],
        vector_field: str,
        top_k: int,
        category_ids: Sequence[str] = (),
    ) -> tuple[PineconeImageMatch, ...]: ...


def discover_query_images(root: Path) -> tuple[Path, ...]:
    """Find supported images recursively in stable path order."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise QueryImageError(f"Query-image directory does not exist: {root}")

    images = tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file()
                and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            ),
            key=lambda path: path.as_posix(),
        )
    )
    if not images:
        raise QueryImageError(f"No supported query images found under: {root}")
    return images


def select_query_image(
    root: Path,
    *,
    randomize: bool = False,
    seed: int | None = None,
) -> Path:
    """Select the first query image, or a reproducible random image."""
    images = discover_query_images(root)
    if not randomize:
        return images[0]
    return random.Random(seed).choice(images)


def validate_query_image(path: Path) -> Path:
    """Resolve and validate an explicitly selected query image."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise QueryImageError(f"Query image does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise QueryImageError(
            f"Unsupported query image extension: {path.suffix or '<none>'}"
        )
    return path


def normalize_category_ids(category_ids: Sequence[str]) -> tuple[str, ...]:
    """Validate, de-duplicate, and preserve requested category order."""
    normalized = tuple(dict.fromkeys(category_ids))
    invalid = [
        category_id
        for category_id in normalized
        if category_id not in CANONICAL_CATEGORY_IDS
    ]
    if invalid:
        raise QueryImageError(
            "Unknown category IDs: " + ", ".join(repr(value) for value in invalid)
        )
    return normalized


def search_similar_images(
    *,
    query_image: Path,
    embedder: QueryImageEmbedder,
    searcher: ImageVectorSearcher,
    vector_field: str,
    top_k: int,
    category_ids: Sequence[str] = (),
) -> tuple[PineconeImageMatch, ...]:
    """Embed one image and retrieve its nearest indexed images."""
    query_image = validate_query_image(query_image)
    if top_k <= 0:
        raise QueryImageError("top_k must be positive")
    if not vector_field.strip():
        raise QueryImageError("vector_field must not be empty")

    normalized_categories = normalize_category_ids(category_ids)
    vector = embedder.embed_image(query_image)
    return searcher.search_by_vector(
        vector=vector,
        vector_field=vector_field,
        top_k=top_k,
        category_ids=normalized_categories,
    )


def search_similar_image_bytes(
    *,
    content: bytes,
    embedder: UploadedImageEmbedder,
    searcher: ImageVectorSearcher,
    vector_field: str,
    top_k: int,
    category_ids: Sequence[str] = (),
) -> tuple[PineconeImageMatch, ...]:
    """Embed validated upload bytes and retrieve nearest image documents."""
    if not content:
        raise QueryImageError("Query image content must not be empty")
    if top_k <= 0:
        raise QueryImageError("top_k must be positive")
    if not vector_field.strip():
        raise QueryImageError("vector_field must not be empty")
    normalized_categories = normalize_category_ids(category_ids)
    vector = embedder.embed_image_bytes(content)
    return searcher.search_by_vector(
        vector=vector,
        vector_field=vector_field,
        top_k=top_k,
        category_ids=normalized_categories,
    )
