"""HTTP contract tests for classifier capabilities and top-k predictions."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.dependencies import get_classification_service, get_classifier_registry
from app.classifiers.registry import ClassifierCapability
from app.main import app
from app.services.image_classification import (
    ClassificationPrediction,
    ClassificationResult,
    ClassificationTiming,
)


def _png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (4, 3), color=(20, 30, 40)).save(stream, format="PNG")
    return stream.getvalue()


class FakeRegistry:
    def capabilities(self):  # type: ignore[no-untyped-def]
        return (
            ClassifierCapability("alexnet", "AlexNet", True, "1.0.0", (224, 224)),
            ClassifierCapability("resnet50", "ResNet50", False, None, None),
            ClassifierCapability("vit", "Vision Transformer (ViT)", False, None, None),
        )


class FakeService:
    def classify(self, *, content: bytes, model_id: str, top_k: int):  # type: ignore[no-untyped-def]
        assert content
        assert model_id == "alexnet"
        assert top_k == 5
        return ClassificationResult(
            model_id="alexnet",
            display_name="AlexNet",
            version="1.0.0",
            predictions=(
                ClassificationPrediction(1, "02", "Áo Thun / Áo Phông", 8.4, 0.87),
                ClassificationPrediction(2, "28", "Áo Khoác Nam Nữ", 5.1, 0.07),
            ),
            suggested_category_id="02",
            timing=ClassificationTiming(1.0, 2.0, 0.5, 3.5),
        )


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_classifier_registry] = lambda: FakeRegistry()
    app.dependency_overrides[get_classification_service] = lambda: FakeService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_classifier_capabilities_expose_available_and_planned_models(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/image-search/classifiers")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == ["alexnet", "resnet50", "vit"]
    assert items[0]["available"] is True
    assert items[1]["available"] is False


def test_classify_returns_ranked_predictions_and_timing(client: TestClient) -> None:
    response = client.post(
        "/api/v1/image-search/classify",
        files={"image": ("query.png", _png_bytes(), "image/png")},
        data={"model_id": "alexnet", "top_k": "5"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggested_category_id"] == "02"
    assert body["predictions"][0]["probability"] == 0.87
    assert body["timing"]["total_ms"] == 3.5

