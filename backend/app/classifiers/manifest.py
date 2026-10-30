"""Versioned classifier artifact manifest loading and validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.classifiers.base import ClassifierLoadError
from app.core.categories import CANONICAL_CATEGORY_IDS


class PreprocessingSpec(BaseModel):
    color_mode: Literal["RGB"] = "RGB"
    resize: tuple[int, int]
    crop: tuple[int, int] | None = None
    interpolation: Literal["bilinear", "bicubic"]
    mean: tuple[float, float, float]
    std: tuple[float, float, float]


class ClassifierMetrics(BaseModel):
    best_epoch: int | None = None
    train_accuracy: float | None = None
    train_loss: float | None = None
    validation_accuracy: float | None = None
    validation_loss: float | None = None
    top5_accuracy: float | None = None
    macro_f1: float | None = None


class ClassifierManifest(BaseModel):
    model_id: str
    display_name: str
    version: str
    architecture: str
    framework: Literal["pytorch"]
    num_classes: int = Field(gt=0)
    checkpoint_format: Literal["state_dict_bundle"]
    checkpoint_file: str
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    class_to_idx: dict[str, int]
    preprocessing: PreprocessingSpec
    metrics: ClassifierMetrics

    @model_validator(mode="after")
    def validate_canonical_mapping(self) -> "ClassifierManifest":
        expected_ids = set(CANONICAL_CATEGORY_IDS)
        if self.num_classes != len(expected_ids):
            raise ValueError("num_classes must match the canonical category count")
        if set(self.class_to_idx) != expected_ids:
            raise ValueError("class_to_idx must contain exactly category IDs 00 through 41")
        if set(self.class_to_idx.values()) != set(range(self.num_classes)):
            raise ValueError("class_to_idx values must be unique indices 0 through 41")
        return self

    @property
    def idx_to_class(self) -> dict[int, str]:
        return {index: category_id for category_id, index in self.class_to_idx.items()}

def load_classifier_manifest(
    manifest_path: Path,
    *,
    verify_checksum: bool = True,
) -> tuple[ClassifierManifest, Path]:
    """Load a manifest and resolve its verified checkpoint within the same folder."""
    manifest_path = manifest_path.expanduser().resolve()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = ClassifierManifest.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ClassifierLoadError("Classifier manifest is invalid") from exc

    checkpoint_path = (manifest_path.parent / manifest.checkpoint_file).resolve()
    if checkpoint_path.parent != manifest_path.parent:
        raise ClassifierLoadError("Classifier checkpoint must be beside its manifest")
    if not checkpoint_path.is_file():
        raise ClassifierLoadError("Classifier checkpoint is missing")
    if verify_checksum:
        digest = hashlib.sha256()
        try:
            with checkpoint_path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ClassifierLoadError("Classifier checkpoint cannot be read") from exc
        if digest.hexdigest().lower() != manifest.checkpoint_sha256.lower():
            raise ClassifierLoadError("Classifier checkpoint checksum does not match")
    return manifest, checkpoint_path

