"""Tests for labeled image discovery and resumable ingestion."""

from typing import Sequence

import pytest

from app.services.image_ingestion import (
    DatasetInventory,
    EmbeddedImage,
    EmbeddingBatch,
    ImageDatasetError,
    ImageSample,
    build_image_sample,
    ingest_images,
    missing_clip_packages,
    validate_category_ids,
)
from app.services.catalog_links import CatalogVectorLink


class FakeEmbedder:
    def embed(self, samples: Sequence[ImageSample]) -> EmbeddingBatch:
        return EmbeddingBatch(
            embedded=tuple(
                EmbeddedImage(sample=sample, values=[0.5, 0.5])
                for sample in samples
            ),
            failures=(),
        )


class FakeWriter:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def upsert(self, documents: list[dict[str, object]]) -> int:
        self.documents.extend(documents)
        return len(documents)


class FakeCheckpoint:
    def __init__(self, ids: set[str] | None = None) -> None:
        self.ids = set(ids or ())

    def load(self) -> set[str]:
        return set(self.ids)

    def append(self, vector_ids: Sequence[str]) -> None:
        self.ids.update(vector_ids)


def test_missing_clip_packages_uses_installable_distribution_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.image_ingestion.importlib.util.find_spec",
        lambda module: None if module in {"torch", "open_clip", "PIL"} else object(),
    )

    assert missing_clip_packages() == ("torch", "open-clip-torch", "Pillow")


def test_build_sample_preserves_two_digit_category_and_stable_id() -> None:
    from pathlib import Path

    root = Path("dataset/train")
    image_path = root / "00" / "product.jpg"

    first = build_image_sample(root, image_path, "00")
    second = build_image_sample(root, image_path, "00")

    assert first.category_id == "00"
    assert first.relative_path == "00/product.jpg"
    assert first.vector_id.startswith("00-")
    assert first.vector_id == second.vector_id


def test_validate_categories_rejects_missing_label_directory() -> None:
    with pytest.raises(ImageDatasetError, match="missing="):
        validate_category_ids({"00"})


def test_ingestion_writes_category_metadata_and_resumes() -> None:
    from pathlib import Path

    sample = ImageSample(
        path=Path("dataset/train/00/product.jpg"),
        relative_path="00/product.jpg",
        category_id="00",
        vector_id="00-stable-id",
    )
    inventory = DatasetInventory(samples=(sample,), ignored_file_count=0)
    checkpoint = FakeCheckpoint()
    writer = FakeWriter()

    first = ingest_images(
        inventory=inventory,
        embedder=FakeEmbedder(),
        writer=writer,
        vector_field="image_vector",
        batch_size=1,
        checkpoint=checkpoint,
    )
    second = ingest_images(
        inventory=inventory,
        embedder=FakeEmbedder(),
        writer=writer,
        vector_field="image_vector",
        batch_size=1,
        checkpoint=checkpoint,
    )

    assert first.upserted == 1
    assert writer.documents == [
        {
            "_id": "00-stable-id",
            "image_vector": [0.5, 0.5],
            "category_id": "00",
            "image_path": "00/product.jpg",
        }
    ]
    assert second.upserted == 0
    assert second.skipped_checkpoint == 1


def test_each_label_limit_is_applied_after_checkpoint_filtering() -> None:
    from pathlib import Path

    samples = (
        ImageSample(Path("00/a.jpg"), "00/a.jpg", "00", "00-a"),
        ImageSample(Path("00/b.jpg"), "00/b.jpg", "00", "00-b"),
        ImageSample(Path("01/a.jpg"), "01/a.jpg", "01", "01-a"),
        ImageSample(Path("01/b.jpg"), "01/b.jpg", "01", "01-b"),
    )
    inventory = DatasetInventory(samples=samples, ignored_file_count=0)
    writer = FakeWriter()
    checkpoint = FakeCheckpoint({"00-a"})

    stats = ingest_images(
        inventory=inventory,
        embedder=FakeEmbedder(),
        writer=writer,
        vector_field="image_vector",
        batch_size=10,
        checkpoint=checkpoint,
        limit=1,
        each_label=True,
    )

    assert stats.skipped_checkpoint == 1
    assert stats.attempted == 2
    assert [document["_id"] for document in writer.documents] == ["00-b", "01-a"]
    assert [document["category_id"] for document in writer.documents] == ["00", "01"]
    assert [document["image_path"] for document in writer.documents] == [
        "00/b.jpg",
        "01/a.jpg",
    ]


def test_each_label_requires_limit() -> None:
    inventory = DatasetInventory(samples=(), ignored_file_count=0)

    with pytest.raises(ValueError, match="requires a limit"):
        ingest_images(
            inventory=inventory,
            embedder=FakeEmbedder(),
            writer=FakeWriter(),
            vector_field="image_vector",
            batch_size=1,
            each_label=True,
        )


def test_ingestion_attaches_catalog_identifiers_when_available() -> None:
    from pathlib import Path

    sample = ImageSample(
        path=Path("dataset/train/00/product.jpg"),
        relative_path="00/product.jpg",
        category_id="00",
        vector_id="00-stable-id",
    )
    writer = FakeWriter()

    ingest_images(
        inventory=DatasetInventory(samples=(sample,), ignored_file_count=0),
        embedder=FakeEmbedder(),
        writer=writer,
        vector_field="image_vector",
        batch_size=1,
        catalog_links={
            "00-stable-id": CatalogVectorLink(
                product_id="product-1",
                image_id="image-1",
            )
        },
    )

    assert writer.documents[0]["product_id"] == "product-1"
    assert writer.documents[0]["image_id"] == "image-1"
