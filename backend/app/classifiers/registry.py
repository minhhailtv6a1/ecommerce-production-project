"""Discover model artifacts and lazily reuse classifier instances."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.classifiers.alexnet import AlexNetClassifier
from app.classifiers.base import (
    ClassifierLoadError,
    ClassifierUnavailableError,
    ImageClassifier,
    UnknownClassifierError,
)
from app.classifiers.manifest import ClassifierManifest, load_classifier_manifest


@dataclass(frozen=True)
class ClassifierCapability:
    id: str
    display_name: str
    available: bool
    version: str | None
    input_size: tuple[int, int] | None


class ClassifierRegistry:
    """Validate versioned artifacts and load each model at most once."""

    _KNOWN_MODELS = {
        "alexnet": "AlexNet",
        "resnet50": "ResNet50",
        "vit": "Vision Transformer (ViT)",
    }

    def __init__(self, artifact_root: Path, *, device: str = "auto") -> None:
        self._artifact_root = artifact_root.expanduser().resolve()
        self._device = device
        self._artifacts: dict[str, tuple[ClassifierManifest, Path]] = {}
        self._instances: dict[str, ImageClassifier] = {}
        self._lock = Lock()
        self._discover_artifacts()

    def _discover_artifacts(self) -> None:
        for model_id in self._KNOWN_MODELS:
            model_root = self._artifact_root / model_id
            manifests = sorted(model_root.glob("*/manifest.json"), reverse=True)
            if not manifests:
                continue
            try:
                manifest, checkpoint = load_classifier_manifest(manifests[0])
            except ClassifierLoadError:
                continue
            if manifest.model_id != model_id:
                continue
            self._artifacts[model_id] = (manifest, checkpoint)

    def capabilities(self) -> tuple[ClassifierCapability, ...]:
        return tuple(
            self._capability(model_id, display_name)
            for model_id, display_name in self._KNOWN_MODELS.items()
        )

    def _capability(self, model_id: str, display_name: str) -> ClassifierCapability:
        artifact = self._artifacts.get(model_id)
        if artifact is None:
            return ClassifierCapability(model_id, display_name, False, None, None)
        manifest, _ = artifact
        return ClassifierCapability(
            model_id,
            manifest.display_name,
            True,
            manifest.version,
            manifest.preprocessing.resize,
        )

    def get_manifest(self, model_id: str) -> ClassifierManifest:
        self._require_known(model_id)
        artifact = self._artifacts.get(model_id)
        if artifact is None:
            raise ClassifierUnavailableError(f"Classifier {model_id!r} is unavailable")
        return artifact[0]

    def get(self, model_id: str) -> ImageClassifier:
        self._require_known(model_id)
        artifact = self._artifacts.get(model_id)
        if artifact is None:
            raise ClassifierUnavailableError(f"Classifier {model_id!r} is unavailable")
        with self._lock:
            existing = self._instances.get(model_id)
            if existing is not None:
                return existing
            manifest, checkpoint = artifact
            if manifest.architecture != "custom_alexnet_v1":
                raise ClassifierLoadError("Classifier architecture is not implemented")
            instance = AlexNetClassifier(
                manifest=manifest,
                checkpoint_path=checkpoint,
                device=self._device,
            )
            self._instances[model_id] = instance
            return instance

    def _require_known(self, model_id: str) -> None:
        if model_id not in self._KNOWN_MODELS:
            raise UnknownClassifierError(f"Unknown classifier: {model_id!r}")

