"""HTTP contract tests for categories, product listing, and detail."""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_product_repository, get_product_service
from app.main import app
from app.services.product_service import ProductService
from tests.test_product_service import FakeCatalogRepository, FakeUrlResolver


@pytest.fixture
def client() -> TestClient:
    repository = FakeCatalogRepository()
    service = ProductService(repository, FakeUrlResolver())
    app.dependency_overrides[get_product_repository] = lambda: repository
    app.dependency_overrides[get_product_service] = lambda: service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_categories_and_product_list_are_frontend_ready(client: TestClient) -> None:
    categories = client.get("/api/v1/categories")
    products = client.get(
        "/api/v1/products",
        params=[("category_ids", "00"), ("limit", "20")],
    )

    assert categories.status_code == 200
    assert categories.json()["items"][0]["product_count"] == 200
    assert products.status_code == 200
    body = products.json()
    assert body["total"] == 1
    assert body["items"][0]["category_id"] == "00"
    assert body["items"][0]["primary_image"]["url"].startswith("https://")


def test_product_detail_returns_gallery_and_real_variants(client: TestClient) -> None:
    response = client.get("/api/v1/products/dam-vay-nu-001")

    assert response.status_code == 200
    body = response.json()
    assert len(body["images"]) == 1
    assert len(body["variants"]) == 1
    assert body["variants"][0]["sku"] == "CAT00-0001-DEFAULT"


def test_catalog_rejects_unknown_category(client: TestClient) -> None:
    response = client.get("/api/v1/products", params={"category_ids": "42"})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
