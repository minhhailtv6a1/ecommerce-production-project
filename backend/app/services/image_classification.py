"""Image-classification orchestration and top-k postprocessing."""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter

from app.classifiers.registry import ClassifierRegistry
from app.core.categories import CLASS_LABELS


@dataclass(frozen=True)
class ClassificationPrediction:
    rank: int
    category_id: str
    label: str
    logit: float
    probability: float


@dataclass(frozen=True)
class ClassificationTiming:
    preprocess_ms: float
    inference_ms: float
    postprocess_ms: float
    total_ms: float


@dataclass(frozen=True)
class ClassificationResult:
    model_id: str
    display_name: str
    version: str
    predictions: tuple[ClassificationPrediction, ...]
    suggested_category_id: str
    timing: ClassificationTiming


class ImageClassificationService:
    def __init__(self, registry: ClassifierRegistry) -> None:
        self._registry = registry

    def classify(
        self,
        *,
        content: bytes,
        model_id: str,
        top_k: int,
    ) -> ClassificationResult:
        total_started = perf_counter()
        manifest = self._registry.get_manifest(model_id)
        classifier = self._registry.get(model_id)
        output = classifier.predict_logits(content)

        postprocess_started = perf_counter()
        max_logit = max(output.logits)
        exponentials = [math.exp(value - max_logit) for value in output.logits]
        denominator = sum(exponentials)
        probabilities = [value / denominator for value in exponentials]
        ranked_indices = sorted(
            range(len(output.logits)),
            key=lambda index: output.logits[index],
            reverse=True,
        )[:top_k]
        predictions = tuple(
            ClassificationPrediction(
                rank=rank,
                category_id=manifest.idx_to_class[index],
                label=CLASS_LABELS[manifest.idx_to_class[index]],
                logit=round(output.logits[index], 6),
                probability=round(probabilities[index], 6),
            )
            for rank, index in enumerate(ranked_indices, start=1)
        )
        postprocess_ms = (perf_counter() - postprocess_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000

        return ClassificationResult(
            model_id=classifier.model_id,
            display_name=classifier.display_name,
            version=classifier.version,
            predictions=predictions,
            suggested_category_id=predictions[0].category_id,
            timing=ClassificationTiming(
                preprocess_ms=output.preprocess_ms,
                inference_ms=output.inference_ms,
                postprocess_ms=round(postprocess_ms, 2),
                total_ms=round(total_ms, 2),
            ),
        )

