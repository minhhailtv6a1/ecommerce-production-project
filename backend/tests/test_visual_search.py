"""Tests for visual-search deduplication and ranking hydration."""

from app.repositories.pinecone import PineconeImageMatch
from app.services.product_service import ProductService
from app.services.visual_search import hydrate_visual_search_matches
from tests.test_product_service import (
    PRODUCT_ID,
    FakeCatalogRepository,
    FakeUrlResolver,
)


def test_visual_search_deduplicates_and_skips_unlinked_or_deleted_products() -> None:
    product_service = ProductService(FakeCatalogRepository(), FakeUrlResolver())
    matches = (
        PineconeImageMatch("v1", 0.95, "00", "00/a.jpg", PRODUCT_ID, "i1"),
        PineconeImageMatch("v2", 0.90, "00", "00/b.jpg", PRODUCT_ID, "i2"),
        PineconeImageMatch("legacy", 0.89, "00", "00/c.jpg"),
        PineconeImageMatch("deleted", 0.88, "00", "00/d.jpg", "deleted", "i4"),
    )

    response = hydrate_visual_search_matches(
        matches,
        product_service=product_service,
        limit=20,
    )

    assert len(response.items) == 1
    assert response.items[0].similarity_score == 0.95
    assert str(response.items[0].product.id) == PRODUCT_ID
