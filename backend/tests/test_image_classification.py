"""Tests for classifier manifests and top-k classification postprocessing."""

import math
from pathlib import Path

from app.classifiers.base import LogitOutput
from app.classifiers.manifest import load_classifier_manifest
from app.services.image_classification import ImageClassificationService


class FakeClassifier:
    model_id = "alexnet"
    display_name = "AlexNet"
    version = "1.0.0"

    def predict_logits(self, content: bytes) -> LogitOutput:
        assert content == b"validated-image"
        return LogitOutput(
            logits=tuple(float(index) for index in range(42)),
            preprocess_ms=2.0,
            inference_ms=3.0,
        )


class FakeRegistry:
    def __init__(self, manifest):  # type: ignore[no-untyped-def]
        self.manifest = manifest
        self.classifier = FakeClassifier()

    def get_manifest(self, model_id: str):  # type: ignore[no-untyped-def]
        assert model_id == "alexnet"
        return self.manifest

    def get(self, model_id: str):  # type: ignore[no-untyped-def]
        assert model_id == "alexnet"
        return self.classifier


def test_alexnet_manifest_matches_canonical_imagefolder_mapping() -> None:
    manifest_path = (
        Path(__file__).parents[1]
        / "artifacts"
        / "classifiers"
        / "alexnet"
        / "1.0.0"
        / "manifest.json"
    )
    manifest, checkpoint = load_classifier_manifest(
        manifest_path,
        verify_checksum=False,
    )

    assert checkpoint.name == "model.pth"
    assert manifest.num_classes == 42
    assert manifest.class_to_idx == {
        f"{index:02d}": index for index in range(42)
    }
    assert manifest.preprocessing.resize == (224, 224)
    assert manifest.metrics.best_epoch == 8


def test_classification_returns_descending_top_five_softmax_predictions() -> None:
    manifest_path = (
        Path(__file__).parents[1]
        / "artifacts"
        / "classifiers"
        / "alexnet"
        / "1.0.0"
        / "manifest.json"
    )
    manifest, _ = load_classifier_manifest(manifest_path, verify_checksum=False)
    service = ImageClassificationService(FakeRegistry(manifest))  # type: ignore[arg-type]

    result = service.classify(
        content=b"validated-image",
        model_id="alexnet",
        top_k=5,
    )

    assert [item.category_id for item in result.predictions] == [
        "41",
        "40",
        "39",
        "38",
        "37",
    ]
    assert result.suggested_category_id == "41"
    assert all(
        left.probability > right.probability
        for left, right in zip(
            result.predictions,
            result.predictions[1:],
            strict=False,
        )
    )
    assert math.isclose(
        result.predictions[0].probability,
        1 - math.exp(-1),
        rel_tol=1e-5,
    )

