"""Custom AlexNet architecture and production inference adapter."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

from app.classifiers.base import (
    ClassificationInferenceError,
    ClassifierLoadError,
    LogitOutput,
)
from app.classifiers.manifest import ClassifierManifest


class AlexNetClassifier:
    """Load and run the custom AlexNet defined by the training notebook."""

    def __init__(
        self,
        *,
        manifest: ClassifierManifest,
        checkpoint_path: Path,
        device: str,
    ) -> None:
        try:
            import torch
            import torch.nn as nn
            from PIL import Image
            from torchvision import transforms
            from torchvision.transforms import InterpolationMode
        except ImportError as exc:
            raise ClassifierLoadError("Classifier runtime dependencies are unavailable") from exc

        resolved_device = self._resolve_device(torch, device)

        class CustomAlexNet(nn.Module):
            def __init__(self, num_classes: int) -> None:
                super().__init__()
                self.extract_feature = nn.Sequential(
                    nn.Conv2d(3, 64, kernel_size=11, stride=4, padding=2),
                    nn.ReLU(),
                    nn.MaxPool2d(kernel_size=3, stride=2),
                    nn.Conv2d(64, 192, kernel_size=5, padding=2),
                    nn.ReLU(),
                    nn.MaxPool2d(kernel_size=3, stride=2),
                    nn.Conv2d(192, 384, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.Conv2d(384, 256, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.Conv2d(256, 256, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.MaxPool2d(kernel_size=3, stride=2),
                )
                self.classifier = nn.Sequential(
                    nn.Flatten(),
                    nn.Dropout(0.5),
                    nn.Linear(256 * 6 * 6, 4096),
                    nn.ReLU(),
                    nn.Dropout(0.5),
                    nn.Linear(4096, 4096),
                    nn.ReLU(),
                    nn.Linear(4096, num_classes),
                )

            def forward(self, value: Any) -> Any:
                return self.classifier(self.extract_feature(value))

        model = CustomAlexNet(manifest.num_classes)
        try:
            checkpoint = torch.load(
                checkpoint_path,
                map_location="cpu",
                weights_only=True,
            )
            state_dict = checkpoint["model_state_dict"]
            model.load_state_dict(state_dict, strict=True)
        except (OSError, KeyError, RuntimeError, TypeError) as exc:
            raise ClassifierLoadError("AlexNet checkpoint is incompatible") from exc

        model.to(resolved_device)
        model.eval()

        interpolation = {
            "bilinear": InterpolationMode.BILINEAR,
            "bicubic": InterpolationMode.BICUBIC,
        }[manifest.preprocessing.interpolation]
        operations: list[Any] = [
            transforms.Resize(
                manifest.preprocessing.resize,
                interpolation=interpolation,
                antialias=True,
            )
        ]
        if manifest.preprocessing.crop is not None:
            operations.append(transforms.CenterCrop(manifest.preprocessing.crop))
        operations.extend(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=manifest.preprocessing.mean,
                    std=manifest.preprocessing.std,
                ),
            ]
        )

        self.model_id = manifest.model_id
        self.display_name = manifest.display_name
        self.version = manifest.version
        self._torch = torch
        self._image_type = Image
        self._model = model
        self._transform = transforms.Compose(operations)
        self._device = resolved_device
        self._num_classes = manifest.num_classes

    @staticmethod
    def _resolve_device(torch: Any, requested: str) -> str:
        if requested == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if requested == "cuda" and not torch.cuda.is_available():
            raise ClassifierLoadError("CUDA was requested but is unavailable")
        if requested not in {"cpu", "cuda"}:
            raise ClassifierLoadError("Unsupported classifier device")
        return requested

    def predict_logits(self, content: bytes) -> LogitOutput:
        try:
            preprocess_started = perf_counter()
            with self._image_type.open(BytesIO(content)) as image:
                tensor = self._transform(image.convert("RGB")).unsqueeze(0)
            preprocess_ms = (perf_counter() - preprocess_started) * 1000

            inference_started = perf_counter()
            with self._torch.inference_mode():
                output = self._model(tensor.to(self._device))
            inference_ms = (perf_counter() - inference_started) * 1000
        except Exception as exc:
            raise ClassificationInferenceError("AlexNet inference failed") from exc

        if tuple(output.shape) != (1, self._num_classes):
            raise ClassificationInferenceError("AlexNet returned an invalid output shape")
        if not bool(self._torch.isfinite(output).all()):
            raise ClassificationInferenceError("AlexNet returned non-finite logits")
        return LogitOutput(
            logits=tuple(float(value) for value in output[0].detach().cpu()),
            preprocess_ms=round(preprocess_ms, 2),
            inference_ms=round(inference_ms, 2),
        )

