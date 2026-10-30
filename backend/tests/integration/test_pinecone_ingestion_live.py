"""Opt-in live CLIP-to-Pinecone ingestion smoke test."""

import os
from pathlib import Path

import pytest

from app.core.config import settings
from app.repositories.pinecone import (
    PineconeDocumentRepository,
    create_pinecone_client,
)
from app.services.image_ingestion import (
    DatasetInventory,
    OpenClipImageEmbedder,
    discover_image_dataset,
    ingest_images,
)
from app.services.catalog_links import load_catalog_vector_links
from app.services.pinecone_index import (
    index_definition_from_settings,
    validate_pinecone_index,
)


@pytest.mark.integration
def test_live_clip_embedding_is_upserted_with_category_and_image_path() -> None:
    if os.getenv("RUN_PINECONE_INGEST_INTEGRATION") != "1":
        pytest.skip(
            "Set RUN_PINECONE_INGEST_INTEGRATION=1 to allow model and Pinecone writes"
        )
    if settings.pinecone_api_key is None:
        pytest.fail("PINECONE_API_KEY is required")
    if settings.ingest_dataset_path is None:
        pytest.fail("INGEST_DATASET_PATH is required")
    if not settings.pinecone_namespace:
        pytest.fail("PINECONE_NAMESPACE is required")

    definition = index_definition_from_settings(settings)
    inventory = discover_image_dataset(settings.ingest_dataset_path)
    one_image = DatasetInventory(
        samples=inventory.samples[:1],
        ignored_file_count=inventory.ignored_file_count,
    )
    client = create_pinecone_client(settings.pinecone_api_key.get_secret_value())
    validate_pinecone_index(client, definition)
    index = client.index(definition.name)
    writer = PineconeDocumentRepository(index, settings.pinecone_namespace)
    embedder = OpenClipImageEmbedder(
        model_name=settings.clip_model_name,
        pretrained=settings.clip_pretrained,
        expected_dimension=definition.dimension,
        device=settings.clip_device,
        cache_dir=settings.clip_cache_dir,
    )

    stats = ingest_images(
        inventory=one_image,
        embedder=embedder,
        writer=writer,
        vector_field=definition.vector_field,
        batch_size=1,
        checkpoint=None,
        catalog_links=load_catalog_vector_links(Path("data/product_images.csv")),
    )

    vector_id = one_image.samples[0].vector_id
    response = index.documents.fetch(
        namespace=settings.pinecone_namespace,
        ids=[vector_id],
        include_fields=["category_id", "image_path", "product_id", "image_id"],
    )

    assert stats.upserted == 1
    assert vector_id in response.documents
    assert response.documents[vector_id].category_id == "00"
    assert (
        response.documents[vector_id].image_path
        == one_image.samples[0].relative_path
    )
    assert response.documents[vector_id].product_id
    assert response.documents[vector_id].image_id
