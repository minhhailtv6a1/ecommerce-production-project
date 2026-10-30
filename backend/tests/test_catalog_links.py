"""Tests for catalog-vector manifest validation."""

from pathlib import Path

import pytest

from app.services.catalog_links import CatalogLinkError, load_catalog_vector_links


def test_load_catalog_vector_links_maps_vector_to_relational_ids() -> None:
    manifest = Path("data/product_images.csv")

    links = load_catalog_vector_links(manifest)

    assert len(links) == 8400
    first = next(iter(links.values()))
    assert first.product_id
    assert first.image_id


def test_load_catalog_vector_links_rejects_empty_identifiers() -> None:
    manifest = Path("tests/fixtures/catalog_links_invalid.csv")

    with pytest.raises(CatalogLinkError, match="empty link"):
        load_catalog_vector_links(manifest)
