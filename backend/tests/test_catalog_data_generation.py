import csv
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.core.categories import CANONICAL_CATEGORY_IDS
from app.services.image_ingestion import DatasetInventory, build_image_sample
from scripts.generate_catalog_data import generate_catalog_csvs
from scripts.insert_data import load_catalog_csvs, validate_catalog_relationships


def _inventory(root: Path, per_category: int = 3) -> DatasetInventory:
    samples = []
    for category_id in CANONICAL_CATEGORY_IDS:
        for index in range(per_category):
            path = root / category_id / f"image-{index:03d}.jpg"
            samples.append(build_image_sample(root, path, category_id))
    return DatasetInventory(samples=tuple(samples), ignored_file_count=0)


@contextmanager
def _writable_test_directory():
    root = Path.cwd() / f"pytest-cache-files-catalog-{uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_generate_catalog_csvs_creates_relational_data() -> None:
    with _writable_test_directory() as test_dir:
        output_dir = test_dir / "data"

        stats = generate_catalog_csvs(
            inventory=_inventory(test_dir),
            output_dir=output_dir,
            limit_per_category=2,
        )

        assert stats.categories == 42
        assert stats.products == 84
        assert stats.variants == 84
        assert stats.images == 84
        assert stats.public_urls_populated is False

        datasets = load_catalog_csvs(output_dir)
        validate_catalog_relationships(datasets)
        assert datasets["categories"][0]["id"] == "00"
        assert datasets["categories"][-1]["id"] == "41"
        assert datasets["products"][0]["category_id"] == "00"
        assert datasets["product_images"][0]["source_path"] == "00/image-000.jpg"
        assert datasets["product_images"][0]["public_url"] is None


def test_generate_catalog_csvs_is_deterministic_and_builds_public_urls() -> None:
    with _writable_test_directory() as test_dir:
        first_dir = test_dir / "first"
        second_dir = test_dir / "second"
        inventory = _inventory(test_dir)

        generate_catalog_csvs(
            inventory=inventory,
            output_dir=first_dir,
            limit_per_category=1,
            public_image_base_url="https://images.example.test/base/",
        )
        generate_catalog_csvs(
            inventory=inventory,
            output_dir=second_dir,
            limit_per_category=1,
            public_image_base_url="https://images.example.test/base/",
        )

        for filename in (
            "categories.csv",
            "products.csv",
            "product_variants.csv",
            "product_images.csv",
        ):
            assert (first_dir / filename).read_bytes() == (
                second_dir / filename
            ).read_bytes()

        with (first_dir / "product_images.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            first_image = next(csv.DictReader(stream))
        assert first_image["public_url"].startswith(
            "https://images.example.test/base/catalog/00/"
        )

