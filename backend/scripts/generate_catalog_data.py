"""Generate deterministic mock catalog CSV files from labeled training images."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from app.core.catalog_ids import catalog_ids_for_image
from app.core.categories import CANONICAL_CATEGORY_IDS, CLASS_LABELS
from app.core.config import settings
from app.services.image_ingestion import (
    DatasetInventory,
    ImageSample,
    discover_image_dataset,
)


logger = logging.getLogger(__name__)

DEFAULT_LIMIT_PER_CATEGORY = 200
DEFAULT_OUTPUT_DIR = Path("data")
BASE_CREATED_AT = datetime(2025, 1, 1, tzinfo=UTC)

CATEGORY_BASE_PRICES = {
    "00": 459_000,
    "01": 549_000,
    "02": 199_000,
    "03": 399_000,
    "04": 449_000,
    "05": 299_000,
    "06": 179_000,
    "07": 199_000,
    "08": 349_000,
    "09": 899_000,
    "10": 149_000,
    "11": 4_990_000,
    "12": 399_000,
    "13": 229_000,
    "14": 1_290_000,
    "15": 359_000,
    "16": 399_000,
    "17": 459_000,
    "18": 7_990_000,
    "19": 249_000,
    "20": 1_990_000,
    "21": 599_000,
    "22": 499_000,
    "23": 199_000,
    "24": 1_290_000,
    "25": 299_000,
    "26": 699_000,
    "27": 349_000,
    "28": 599_000,
    "29": 399_000,
    "30": 899_000,
    "31": 79_000,
    "32": 89_000,
    "33": 99_000,
    "34": 299_000,
    "35": 699_000,
    "36": 249_000,
    "37": 9_990_000,
    "38": 399_000,
    "39": 299_000,
    "40": 1_490_000,
    "41": 4_990_000,
}

APPAREL_CATEGORY_IDS = frozenset({"00", "01", "02", "03", "04", "28", "29"})
FOOTWEAR_CATEGORY_IDS = frozenset({"16", "17", "30"})
SIZED_CATEGORY_OPTIONS = {
    "05": ("6", "7", "8", "9"),
    "07": ("M", "L"),
    "22": ("M", "L", "XL"),
    "23": ("M", "L", "XL"),
    "25": ("90 cm", "100 cm", "110 cm"),
}
COLORS = ("Đen", "Trắng", "Xanh navy", "Be", "Xám", "Đỏ")
DEMO_BRANDS = ("Demo Brand A", "Demo Brand B", "Demo Brand C", "Demo Brand D")

CATEGORY_FIELDS = (
    "id",
    "slug",
    "name",
    "description",
    "display_order",
    "is_active",
    "created_at",
)
PRODUCT_FIELDS = (
    "id",
    "slug",
    "name",
    "description",
    "category_id",
    "brand",
    "status",
    "currency",
    "created_at",
    "updated_at",
)
VARIANT_FIELDS = (
    "id",
    "product_id",
    "sku",
    "color",
    "size",
    "price",
    "compare_at_price",
    "inventory_quantity",
    "is_active",
    "created_at",
    "updated_at",
)
IMAGE_FIELDS = (
    "id",
    "product_id",
    "variant_id",
    "pinecone_vector_id",
    "source_path",
    "storage_path",
    "public_url",
    "alt_text",
    "sort_order",
    "is_primary",
    "created_at",
)


@dataclass(frozen=True)
class GenerationStats:
    categories: int
    products: int
    variants: int
    images: int
    output_dir: str
    public_urls_populated: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate categories, products, product variants, and product images "
            "CSV files from the first sorted images in every category directory."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Override INGEST_DATASET_PATH.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="CSV output directory (default: data).",
    )
    parser.add_argument(
        "--limit-per-category",
        type=int,
        default=DEFAULT_LIMIT_PER_CATEGORY,
        help="Number of first sorted images used per category (default: 200).",
    )
    parser.add_argument(
        "--public-image-base-url",
        default=None,
        help=(
            "Optional public base URL for image records. When omitted, public_url "
            "is intentionally empty until images are uploaded or served."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    dataset = args.dataset or settings.ingest_dataset_path
    if dataset is None:
        logger.error("Missing dataset path: use --dataset or INGEST_DATASET_PATH")
        return 2
    if args.limit_per_category <= 0:
        logger.error("--limit-per-category must be positive")
        return 2

    try:
        inventory = discover_image_dataset(dataset)
        stats = generate_catalog_csvs(
            inventory=inventory,
            output_dir=args.output_dir,
            limit_per_category=args.limit_per_category,
            public_image_base_url=args.public_image_base_url,
        )
    except Exception:
        logger.exception("Catalog CSV generation failed")
        return 1

    print(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
    return 0


def generate_catalog_csvs(
    *,
    inventory: DatasetInventory,
    output_dir: Path,
    limit_per_category: int = DEFAULT_LIMIT_PER_CATEGORY,
    public_image_base_url: str | None = None,
) -> GenerationStats:
    """Create four deterministic UTF-8 CSV files and return their row counts."""
    if limit_per_category <= 0:
        raise ValueError("limit_per_category must be positive")

    selected = _select_first_per_category(inventory, limit_per_category)
    counts = Counter(sample.category_id for sample in selected)
    incomplete = {
        category_id: counts[category_id]
        for category_id in CANONICAL_CATEGORY_IDS
        if counts[category_id] != limit_per_category
    }
    if incomplete:
        raise ValueError(
            "Every category must contain at least the requested number of images: "
            + ", ".join(f"{key}={value}" for key, value in incomplete.items())
        )

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base_url = public_image_base_url.rstrip("/") if public_image_base_url else None

    category_rows = list(_category_rows())
    product_rows: list[dict[str, object]] = []
    variant_rows: list[dict[str, object]] = []
    image_rows: list[dict[str, object]] = []

    category_position: Counter[str] = Counter()
    for global_index, sample in enumerate(selected):
        category_position[sample.category_id] += 1
        position = category_position[sample.category_id]
        product_id, variant_id, image_id = catalog_ids_for_image(sample.relative_path)
        category_name = CLASS_LABELS[sample.category_id]
        slug = _product_slug(category_name, sample.relative_path, position)
        created_at = (BASE_CREATED_AT + timedelta(minutes=global_index)).isoformat()
        price = _price_for(sample.category_id, position)
        compare_at_price = price + max(10_000, price // 5) if position % 4 == 0 else ""
        color = COLORS[(position - 1) % len(COLORS)]
        size = _size_for(sample.category_id, position)
        inventory_quantity = 0 if position % 23 == 0 else 5 + (position * 7) % 46
        storage_path = f"catalog/{sample.relative_path}"
        public_url = _public_url(base_url, storage_path)

        product_rows.append(
            {
                "id": product_id,
                "slug": slug,
                "name": f"{category_name} - Mẫu {position:03d}",
                "description": (
                    f"Sản phẩm mô phỏng thuộc danh mục {category_name}, "
                    "được sinh từ bộ ảnh phục vụ phát triển và kiểm thử."
                ),
                "category_id": sample.category_id,
                "brand": DEMO_BRANDS[(position - 1) % len(DEMO_BRANDS)],
                "status": "published",
                "currency": "VND",
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        variant_rows.append(
            {
                "id": variant_id,
                "product_id": product_id,
                "sku": f"CAT{sample.category_id}-{position:04d}-DEFAULT",
                "color": color,
                "size": size,
                "price": price,
                "compare_at_price": compare_at_price,
                "inventory_quantity": inventory_quantity,
                "is_active": "true",
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        image_rows.append(
            {
                "id": image_id,
                "product_id": product_id,
                "variant_id": variant_id,
                "pinecone_vector_id": sample.vector_id,
                "source_path": sample.relative_path,
                "storage_path": storage_path,
                "public_url": public_url,
                "alt_text": f"{category_name} - Mẫu {position:03d}",
                "sort_order": 0,
                "is_primary": "true",
                "created_at": created_at,
            }
        )

    _write_csv(output_dir / "categories.csv", CATEGORY_FIELDS, category_rows)
    _write_csv(output_dir / "products.csv", PRODUCT_FIELDS, product_rows)
    _write_csv(output_dir / "product_variants.csv", VARIANT_FIELDS, variant_rows)
    _write_csv(output_dir / "product_images.csv", IMAGE_FIELDS, image_rows)

    return GenerationStats(
        categories=len(category_rows),
        products=len(product_rows),
        variants=len(variant_rows),
        images=len(image_rows),
        output_dir=str(output_dir),
        public_urls_populated=base_url is not None,
    )


def _select_first_per_category(
    inventory: DatasetInventory, limit_per_category: int
) -> list[ImageSample]:
    counts: Counter[str] = Counter()
    selected = []
    for sample in inventory.samples:
        if counts[sample.category_id] >= limit_per_category:
            continue
        selected.append(sample)
        counts[sample.category_id] += 1
    return selected


def _category_rows() -> Iterable[dict[str, object]]:
    created_at = BASE_CREATED_AT.isoformat()
    for display_order, (category_id, name) in enumerate(CLASS_LABELS.items()):
        yield {
            "id": category_id,
            "slug": _slugify(name),
            "name": name,
            "description": f"Danh mục chuẩn {category_id}: {name}.",
            "display_order": display_order,
            "is_active": "true",
            "created_at": created_at,
        }


def _product_slug(category_name: str, relative_path: str, position: int) -> str:
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:10]
    return f"{_slugify(category_name)}-{position:03d}-{digest}"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("Đ", "D").replace("đ", "d"))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _price_for(category_id: str, position: int) -> int:
    base = CATEGORY_BASE_PRICES[category_id]
    step = max(10_000, base // 20)
    return base + ((position - 1) % 7) * step


def _size_for(category_id: str, position: int) -> str:
    if category_id in APPAREL_CATEGORY_IDS:
        choices = ("S", "M", "L", "XL")
    elif category_id in FOOTWEAR_CATEGORY_IDS:
        choices = tuple(str(size) for size in range(36, 44))
    else:
        choices = SIZED_CATEGORY_OPTIONS.get(category_id, ())
    return choices[(position - 1) % len(choices)] if choices else ""


def _public_url(base_url: str | None, storage_path: str) -> str:
    if base_url is None:
        return ""
    encoded_path = "/".join(quote(part) for part in storage_path.split("/"))
    return f"{base_url}/{encoded_path}"


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, object]],
) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())

