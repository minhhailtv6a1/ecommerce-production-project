"""HTTP contract tests for server-timed visual retrieval."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.dependencies import get_product_service
from app.api.routes import image_search as image_search_route
from app.core.config import settings
from app.main import app
from app.repositories.pinecone import PineconeImageMatch
from app.services.product_service import ProductService
from tests.test_product_service import (
    IMAGE_ID,
    PRODUCT_ID,
    FakeCatalogRepository,
    FakeUrlResolver,
)


def _png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (4, 3), color=(20, 30, 40)).save(stream, format="PNG")
    return stream.getvalue()


def test_image_search_returns_rag_time_and_uses_top_k_50(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ProductService(FakeCatalogRepository(), FakeUrlResolver())
    captured: dict[str, object] = {}

    def fake_search_similar_image_bytes(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return (
            PineconeImageMatch(
                id="vector-1",
                score=0.91,
                category_id="00",
                image_path="00/a.jpg",
                product_id=PRODUCT_ID,
                image_id=IMAGE_ID,
            ),
        )

    clock = iter((10.0, 10.12345))
    monkeypatch.setattr(
        image_search_route,
        "get_image_search_resources",
        lambda: (object(), object(), "image_vector"),
    )
    monkeypatch.setattr(
        image_search_route,
        "search_similar_image_bytes",
        fake_search_similar_image_bytes,
    )
    monkeypatch.setattr(image_search_route, "perf_counter", lambda: next(clock))
    app.dependency_overrides[get_product_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/image-search/search",
            files={"image": ("query.png", _png_bytes(), "image/png")},
            data={"limit": "50"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_time_ms"] == 123.45
    assert len(body["items"]) == 1
    assert captured["top_k"] == settings.image_search_top_k == 50

