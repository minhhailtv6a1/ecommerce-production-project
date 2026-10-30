"""Image discovery, CLIP embedding, and resumable Pinecone ingestion."""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from app.core.categories import CANONICAL_CATEGORY_IDS
from app.services.catalog_links import CatalogVectorLink


logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
)


class ImageDatasetError(ValueError):
    """Raised when the training directory does not match the required layout."""


class ImageEmbeddingDependencyError(RuntimeError):
    """Raised when CLIP inference dependencies cannot be loaded."""


class ImageEmbeddingError(RuntimeError):
    """Raised when CLIP produces an invalid embedding batch."""


def missing_clip_packages() -> tuple[str, ...]:
    """Return distribution names required for CLIP that are not importable."""
    module_packages = (
        ("torch", "torch"),
        ("open_clip", "open-clip-torch"),
        ("PIL", "Pillow"),
    )
    return tuple(
        package
        for module, package in module_packages
        if importlib.util.find_spec(module) is None
    )


@dataclass(frozen=True)
class ImageSample:
    """One source image with its stable Pinecone identity."""

    path: Path
    relative_path: str
    category_id: str
    vector_id: str


@dataclass(frozen=True)
class DatasetInventory:
    """Validated image samples and ignored non-image file count."""

    samples: tuple[ImageSample, ...]
    ignored_file_count: int


@dataclass(frozen=True)
class EmbeddedImage:
    """An image sample and its normalized embedding."""

    sample: ImageSample
    values: list[float]


@dataclass(frozen=True)
class EmbeddingFailure:
    """A source image that could not be decoded or embedded."""

    sample: ImageSample
    error: str


@dataclass(frozen=True)
class EmbeddingBatch:
    """Successful and failed items from one inference batch."""

    embedded: tuple[EmbeddedImage, ...]
    failures: tuple[EmbeddingFailure, ...]


@dataclass(frozen=True)
class IngestionStats:
    """Counters reported by one ingestion run."""

    discovered: int
    ignored_files: int
    skipped_checkpoint: int
    attempted: int
    upserted: int
    failed: int


class ImageEmbedder(Protocol):
    """Batch image embedding interface used by the pipeline."""

    def embed(self, samples: Sequence[ImageSample]) -> EmbeddingBatch: ...


class DocumentWriter(Protocol):
    """Pinecone document writer interface used by the pipeline."""

    def upsert(self, documents: list[dict[str, Any]]) -> int: ...


class Checkpoint(Protocol):
    """Resume checkpoint interface used by the pipeline."""

    def load(self) -> set[str]: ...

    def append(self, vector_ids: Sequence[str]) -> None: ...


class IngestionCheckpoint:
    """Append-only local record of successfully upserted vector IDs."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self.path.open("r", encoding="utf-8") as stream:
            return {line.strip() for line in stream if line.strip()}

    def append(self, vector_ids: Sequence[str]) -> None:
        if not vector_ids:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            for vector_id in vector_ids:
                stream.write(f"{vector_id}\n")
            stream.flush()
            os.fsync(stream.fileno())


class OpenClipImageEmbedder:
    """Generate normalized OpenAI CLIP image embeddings with OpenCLIP."""

    def __init__(
        self,
        *,
        model_name: str,
        pretrained: str,
        expected_dimension: int,
        device: str = "auto",
        cache_dir: Path | None = None,
    ) -> None:
        missing_packages = missing_clip_packages()
        if missing_packages:
            package_list = " ".join(missing_packages)
            raise ImageEmbeddingDependencyError(
                "Missing CLIP dependencies: "
                + ", ".join(missing_packages)
                + ". Install them in the active environment with: "
                + f"python -m pip install {package_list}"
            )

        try:
            import open_clip
            import torch
            from PIL import Image
        except ImportError as exc:
            raise ImageEmbeddingDependencyError(
                "A CLIP dependency could not be imported"
                + (f": {exc.name}" if exc.name else "")
                + ". Reinstall the runtime dependencies with: "
                + "python -m pip install -r requirements.txt"
            ) from exc

        resolved_device = self._resolve_device(torch, device)
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=pretrained,
            device=resolved_device,
            cache_dir=str(cache_dir) if cache_dir is not None else None,
        )
        model.eval()

        self._torch = torch
        self._image_type = Image
        self._model = model
        self._preprocess = preprocess
        self.device = resolved_device
        self.expected_dimension = expected_dimension

    def embed_image(self, path: Path) -> list[float]:
        """Embed one query image with the same preprocessing as ingestion."""
        path = path.expanduser().resolve()
        if not path.is_file():
            raise ImageEmbeddingError(f"Query image does not exist: {path}")
        try:
            tensor = self._preprocess_image(path)
        except Exception as exc:
            raise ImageEmbeddingError(
                f"Unable to decode query image {path.name!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return self._encode_tensors([tensor])[0]

    def embed_image_bytes(self, content: bytes) -> list[float]:
        """Embed already-validated encoded image bytes without a temp file."""
        try:
            with self._image_type.open(BytesIO(content)) as image:
                tensor = self._preprocess(image.convert("RGB"))
        except Exception as exc:
            raise ImageEmbeddingError(
                f"Unable to decode query image: {type(exc).__name__}: {exc}"
            ) from exc
        return self._encode_tensors([tensor])[0]

    @staticmethod
    def _resolve_device(torch: Any, requested: str) -> str:
        if requested == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if requested == "cuda" and not torch.cuda.is_available():
            raise ImageEmbeddingError(
                "CLIP_DEVICE=cuda was requested, but CUDA is unavailable"
            )
        if requested not in {"cpu", "cuda"}:
            raise ImageEmbeddingError(f"Unsupported CLIP device: {requested!r}")
        return requested

    def embed(self, samples: Sequence[ImageSample]) -> EmbeddingBatch:
        tensors: list[Any] = []
        valid_samples: list[ImageSample] = []
        failures: list[EmbeddingFailure] = []

        for sample in samples:
            try:
                tensors.append(self._preprocess_image(sample.path))
                valid_samples.append(sample)
            except Exception as exc:
                failures.append(
                    EmbeddingFailure(
                        sample=sample,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        if not tensors:
            return EmbeddingBatch(embedded=(), failures=tuple(failures))

        values = self._encode_tensors(tensors)
        embedded = tuple(
            EmbeddedImage(sample=sample, values=vector)
            for sample, vector in zip(valid_samples, values, strict=True)
        )
        return EmbeddingBatch(embedded=embedded, failures=tuple(failures))

    def _preprocess_image(self, path: Path) -> Any:
        with self._image_type.open(path) as image:
            return self._preprocess(image.convert("RGB"))

    def _encode_tensors(self, tensors: Sequence[Any]) -> list[list[float]]:
        batch = self._torch.stack(tensors).to(self.device)
        with self._torch.inference_mode():
            features = self._model.encode_image(batch)
            norms = features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
            features = features / norms

        if features.ndim != 2 or features.shape[1] != self.expected_dimension:
            raise ImageEmbeddingError(
                "CLIP embedding dimension mismatch: "
                f"expected {self.expected_dimension}, got {tuple(features.shape)}"
            )
        if not bool(self._torch.isfinite(features).all()):
            raise ImageEmbeddingError("CLIP produced non-finite embedding values")

        return features.detach().cpu().float().tolist()


def discover_image_dataset(root: Path) -> DatasetInventory:
    """Validate label folders and discover supported images deterministically."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ImageDatasetError(f"Training directory does not exist: {root}")

    actual_categories = {path.name for path in root.iterdir() if path.is_dir()}
    validate_category_ids(actual_categories)

    samples: list[ImageSample] = []
    ignored_file_count = 0
    for category_id in CANONICAL_CATEGORY_IDS:
        category_dir = root / category_id
        for path in sorted(
            (item for item in category_dir.rglob("*") if item.is_file()),
            key=lambda item: item.as_posix(),
        ):
            if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                ignored_file_count += 1
                continue
            samples.append(build_image_sample(root, path, category_id))

    if not samples:
        raise ImageDatasetError(f"No supported images found under: {root}")
    return DatasetInventory(
        samples=tuple(samples),
        ignored_file_count=ignored_file_count,
    )


def validate_category_ids(actual_categories: set[str]) -> None:
    """Require exactly the canonical two-digit category directory names."""
    expected_categories = set(CANONICAL_CATEGORY_IDS)
    missing = sorted(expected_categories - actual_categories)
    unexpected = sorted(actual_categories - expected_categories)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise ImageDatasetError(
            "Training directory must contain exactly labels 00 through 41 ("
            + "; ".join(details)
            + ")"
        )


def build_image_sample(root: Path, path: Path, category_id: str) -> ImageSample:
    """Build a sample whose ID is stable for a dataset-relative image path."""
    if category_id not in CANONICAL_CATEGORY_IDS:
        raise ImageDatasetError(f"Unknown category ID: {category_id!r}")
    relative_path = path.relative_to(root).as_posix()
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
    return ImageSample(
        path=path,
        relative_path=relative_path,
        category_id=category_id,
        vector_id=f"{category_id}-{digest}",
    )


def ingest_images(
    *,
    inventory: DatasetInventory,
    embedder: ImageEmbedder,
    writer: DocumentWriter,
    vector_field: str,
    batch_size: int,
    checkpoint: Checkpoint | None = None,
    limit: int | None = None,
    each_label: bool = False,
    catalog_links: Mapping[str, CatalogVectorLink] | None = None,
) -> IngestionStats:
    """Embed images in batches and upsert labeled Pinecone documents."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive when provided")
    if each_label and limit is None:
        raise ValueError("each_label requires a limit")

    completed_ids = checkpoint.load() if checkpoint is not None else set()
    pending = [
        sample for sample in inventory.samples if sample.vector_id not in completed_ids
    ]
    skipped_checkpoint = len(inventory.samples) - len(pending)
    pending = _apply_limit(pending, limit=limit, each_label=each_label)

    upserted = 0
    failed = 0
    for offset in range(0, len(pending), batch_size):
        batch_samples = pending[offset : offset + batch_size]
        result = embedder.embed(batch_samples)
        for failure in result.failures:
            logger.error(
                "Failed to embed %s: %s",
                failure.sample.relative_path,
                failure.error,
            )
        failed += len(result.failures)

        documents = []
        for item in result.embedded:
            document: dict[str, Any] = {
                "_id": item.sample.vector_id,
                vector_field: item.values,
                "category_id": item.sample.category_id,
                "image_path": item.sample.relative_path,
            }
            link = (catalog_links or {}).get(item.sample.vector_id)
            if link is not None:
                document["product_id"] = link.product_id
                document["image_id"] = link.image_id
            documents.append(document)
        accepted = writer.upsert(documents)
        if accepted != len(documents):
            raise RuntimeError(
                "Pinecone accepted an unexpected document count: "
                f"expected {len(documents)}, got {accepted}"
            )

        successful_ids = [item.sample.vector_id for item in result.embedded]
        if checkpoint is not None:
            checkpoint.append(successful_ids)
        upserted += accepted
        logger.info(
            "Ingestion progress: processed=%d/%d, upserted=%d, failed=%d",
            min(offset + len(batch_samples), len(pending)),
            len(pending),
            upserted,
            failed,
        )

    return IngestionStats(
        discovered=len(inventory.samples),
        ignored_files=inventory.ignored_file_count,
        skipped_checkpoint=skipped_checkpoint,
        attempted=len(pending),
        upserted=upserted,
        failed=failed,
    )


def _apply_limit(
    samples: Sequence[ImageSample],
    *,
    limit: int | None,
    each_label: bool,
) -> list[ImageSample]:
    if limit is None:
        return list(samples)
    if not each_label:
        return list(samples[:limit])

    selected: list[ImageSample] = []
    counts = {category_id: 0 for category_id in CANONICAL_CATEGORY_IDS}
    for sample in samples:
        if counts[sample.category_id] >= limit:
            continue
        selected.append(sample)
        counts[sample.category_id] += 1
    return selected
