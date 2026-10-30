"""Shared classifier domain types and errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ClassifierError(RuntimeError):
    """Base error for classifier configuration and inference."""


class UnknownClassifierError(ClassifierError):
    """Raised when a model identifier is not registered."""


class ClassifierUnavailableError(ClassifierError):
    """Raised when a known model has no usable artifact."""


class ClassifierLoadError(ClassifierError):
    """Raised when a model artifact cannot be validated or loaded."""


class ClassificationInferenceError(ClassifierError):
    """Raised when preprocessing or inference fails."""


@dataclass(frozen=True)
class LogitOutput:
    """One-model inference output before softmax postprocessing."""

    logits: tuple[float, ...]
    preprocess_ms: float
    inference_ms: float


class ImageClassifier(Protocol):
    """Runtime contract implemented by every classification model."""

    model_id: str
    display_name: str
    version: str

    def predict_logits(self, content: bytes) -> LogitOutput: ...

