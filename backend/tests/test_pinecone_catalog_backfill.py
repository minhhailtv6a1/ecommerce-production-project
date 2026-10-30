"""Tests for non-destructive Pinecone catalog metadata backfill."""

from app.services.catalog_links import CatalogVectorLink
from scripts.backfill_pinecone_catalog_metadata import build_metadata_patches


def test_build_metadata_patches_does_not_include_vector_field() -> None:
    patches = build_metadata_patches(
        {
            "00-vector": CatalogVectorLink(
                product_id="product-1",
                image_id="image-1",
            )
        }
    )

    assert patches == [
        {
            "_id": "00-vector",
            "product_id": "product-1",
            "image_id": "image-1",
        }
    ]
