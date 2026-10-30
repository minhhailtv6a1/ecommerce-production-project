"""Opt-in live CLIP-to-Pinecone image-search smoke test."""

import os

import pytest

from app.core.config import settings
from app.repositories.pinecone import (
    PineconeDocumentRepository,
    create_pinecone_client,
)
from app.services.image_ingestion import OpenClipImageEmbedder
from app.services.image_search import search_similar_images, select_query_image
from app.services.pinecone_index import (
    index_definition_from_settings,
    validate_pinecone_index,
)


@pytest.mark.integration
def test_live_test_image_returns_ranked_pinecone_matches() -> None:
    if os.getenv("RUN_PINECONE_SEARCH_INTEGRATION") != "1":
        pytest.skip(
            "Set RUN_PINECONE_SEARCH_INTEGRATION=1 to run live CLIP search"
        )
    if settings.pinecone_api_key is None:
        pytest.fail("PINECONE_API_KEY is required")
    if not settings.pinecone_namespace:
        pytest.fail("PINECONE_NAMESPACE is required")

    test_dir = settings.search_test_dataset_path
    if test_dir is None and settings.ingest_dataset_path is not None:
        test_dir = settings.ingest_dataset_path.parent / "test"
    if test_dir is None:
        pytest.fail("SEARCH_TEST_DATASET_PATH is required")

    definition = index_definition_from_settings(settings)
    client = create_pinecone_client(settings.pinecone_api_key.get_secret_value())
    validate_pinecone_index(client, definition)
    repository = PineconeDocumentRepository(
        client.index(definition.name),
        settings.pinecone_namespace,
    )
    embedder = OpenClipImageEmbedder(
        model_name=settings.clip_model_name,
        pretrained=settings.clip_pretrained,
        expected_dimension=definition.dimension,
        device=settings.clip_device,
        cache_dir=settings.clip_cache_dir,
    )

    matches = search_similar_images(
        query_image=select_query_image(test_dir),
        embedder=embedder,
        searcher=repository,
        vector_field=definition.vector_field,
        top_k=5,
    )

    assert len(matches) == 5
    assert all(match.category_id is not None for match in matches)
    assert all(match.image_path is not None for match in matches)
    assert [match.score for match in matches] == sorted(
        (match.score for match in matches),
        reverse=True,
    )
