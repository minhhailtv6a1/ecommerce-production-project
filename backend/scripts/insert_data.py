"""Create catalog tables and idempotently load generated CSV data into Supabase."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.categories import CANONICAL_CATEGORY_IDS
from app.repositories.database import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    open_database_connection,
)


logger = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path("data")
DEFAULT_BATCH_SIZE = 500

CREATE_CATALOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS public.categories (
    id CHAR(2) PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    display_order SMALLINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT categories_id_format CHECK (id ~ '^[0-9]{2}$'),
    CONSTRAINT categories_display_order_nonnegative CHECK (display_order >= 0)
);

CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    category_id CHAR(2) NOT NULL REFERENCES public.categories(id),
    brand TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    currency CHAR(3) NOT NULL DEFAULT 'VND',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT products_status_allowed
        CHECK (status IN ('draft', 'published', 'archived')),
    CONSTRAINT products_currency_format CHECK (currency ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS public.product_variants (
    id UUID PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    sku TEXT NOT NULL UNIQUE,
    color TEXT,
    size TEXT,
    price BIGINT NOT NULL,
    compare_at_price BIGINT,
    inventory_quantity INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT product_variants_price_nonnegative CHECK (price >= 0),
    CONSTRAINT product_variants_compare_price_valid
        CHECK (compare_at_price IS NULL OR compare_at_price >= price),
    CONSTRAINT product_variants_inventory_nonnegative
        CHECK (inventory_quantity >= 0)
);

CREATE TABLE IF NOT EXISTS public.product_images (
    id UUID PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES public.product_variants(id) ON DELETE SET NULL,
    pinecone_vector_id TEXT NOT NULL UNIQUE,
    source_path TEXT NOT NULL UNIQUE,
    storage_path TEXT NOT NULL UNIQUE,
    public_url TEXT,
    alt_text TEXT NOT NULL,
    sort_order SMALLINT NOT NULL DEFAULT 0,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT product_images_sort_order_nonnegative CHECK (sort_order >= 0)
);

CREATE INDEX IF NOT EXISTS products_category_status_idx
    ON public.products (category_id, status);
CREATE INDEX IF NOT EXISTS products_created_at_idx
    ON public.products (created_at DESC);
CREATE INDEX IF NOT EXISTS product_variants_product_id_idx
    ON public.product_variants (product_id);
CREATE INDEX IF NOT EXISTS product_variants_filter_idx
    ON public.product_variants (color, size, price, is_active);
CREATE INDEX IF NOT EXISTS product_images_product_id_idx
    ON public.product_images (product_id, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS product_images_one_primary_per_product_idx
    ON public.product_images (product_id) WHERE is_primary;
"""


@dataclass(frozen=True)
class TableSpec:
    name: str
    filename: str
    columns: tuple[str, ...]
    nullable_columns: frozenset[str]
    integer_columns: frozenset[str]
    boolean_columns: frozenset[str]
    conflict_column: str = "id"

    @property
    def upsert_sql(self) -> str:
        quoted_columns = ", ".join(self.columns)
        placeholders = ", ".join(f"%({column})s" for column in self.columns)
        update_columns = [
            column for column in self.columns if column != self.conflict_column
        ]
        updates = ", ".join(
            f"{column} = EXCLUDED.{column}" for column in update_columns
        )
        return (
            f"INSERT INTO public.{self.name} ({quoted_columns}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({self.conflict_column}) DO UPDATE SET {updates}"
        )


TABLE_SPECS = (
    TableSpec(
        name="categories",
        filename="categories.csv",
        columns=(
            "id",
            "slug",
            "name",
            "description",
            "display_order",
            "is_active",
            "created_at",
        ),
        nullable_columns=frozenset({"description"}),
        integer_columns=frozenset({"display_order"}),
        boolean_columns=frozenset({"is_active"}),
    ),
    TableSpec(
        name="products",
        filename="products.csv",
        columns=(
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
        ),
        nullable_columns=frozenset({"description", "brand"}),
        integer_columns=frozenset(),
        boolean_columns=frozenset(),
    ),
    TableSpec(
        name="product_variants",
        filename="product_variants.csv",
        columns=(
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
        ),
        nullable_columns=frozenset({"color", "size", "compare_at_price"}),
        integer_columns=frozenset(
            {"price", "compare_at_price", "inventory_quantity"}
        ),
        boolean_columns=frozenset({"is_active"}),
    ),
    TableSpec(
        name="product_images",
        filename="product_images.csv",
        columns=(
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
        ),
        nullable_columns=frozenset({"variant_id", "public_url"}),
        integer_columns=frozenset({"sort_order"}),
        boolean_columns=frozenset({"is_primary"}),
    ),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create the Supabase PostgreSQL catalog schema and upsert all rows "
            "from the generated CSV files."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Connect, create tables/indexes, and upsert data. Default: dry run.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the four catalog CSV files.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Rows per executemany batch (default: 500).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        logger.error("--batch-size must be positive")
        return 2

    try:
        datasets = load_catalog_csvs(args.data_dir)
        validate_catalog_relationships(datasets)
    except (OSError, ValueError) as exc:
        logger.error("%s", exc)
        return 2

    plan = {
        "action": "apply" if args.apply else "plan",
        "schema": "public",
        "data_dir": str(args.data_dir.resolve()),
        "tables": {spec.name: len(datasets[spec.name]) for spec in TABLE_SPECS},
        "write_mode": "create-if-missing-and-upsert",
        "destructive_operations": False,
        "batch_size": args.batch_size,
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        logger.info("Dry run only. Add --apply to write to Supabase PostgreSQL.")
        return 0

    try:
        connection = open_database_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(CREATE_CATALOG_SCHEMA_SQL)
            validate_database_schema(connection)
            for spec in TABLE_SPECS:
                rows = datasets[spec.name]
                upsert_rows(connection, spec, rows, args.batch_size)
                logger.info("Upserted %d rows into public.%s", len(rows), spec.name)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Catalog schema creation/import failed; transaction rolled back")
        return 1

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def load_catalog_csvs(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Read and type-convert every required CSV, failing before any DB write."""
    data_dir = data_dir.resolve()
    datasets: dict[str, list[dict[str, Any]]] = {}
    for spec in TABLE_SPECS:
        path = data_dir / spec.filename
        if not path.is_file():
            raise ValueError(f"Missing required CSV file: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            actual_columns = tuple(reader.fieldnames or ())
            if actual_columns != spec.columns:
                raise ValueError(
                    f"Unexpected columns in {path.name}: expected {spec.columns}, "
                    f"got {actual_columns}"
                )
            datasets[spec.name] = [
                _convert_row(spec, row, row_number)
                for row_number, row in enumerate(reader, start=2)
            ]
        if not datasets[spec.name]:
            raise ValueError(f"CSV file has no data rows: {path}")
    return datasets


def validate_catalog_relationships(
    datasets: dict[str, list[dict[str, Any]]],
) -> None:
    """Validate canonical categories, foreign keys, and one primary image per item."""
    category_ids = {row["id"] for row in datasets["categories"]}
    if category_ids != set(CANONICAL_CATEGORY_IDS):
        raise ValueError("categories.csv must contain exactly category IDs 00 through 41")

    products = datasets["products"]
    product_ids = {row["id"] for row in products}
    if len(product_ids) != len(products):
        raise ValueError("products.csv contains duplicate product IDs")
    unknown_categories = sorted(
        {row["category_id"] for row in products} - category_ids
    )
    if unknown_categories:
        raise ValueError(f"Products reference unknown categories: {unknown_categories}")

    variants = datasets["product_variants"]
    variant_ids = {row["id"] for row in variants}
    unknown_variant_products = {row["product_id"] for row in variants} - product_ids
    if unknown_variant_products:
        raise ValueError("product_variants.csv references unknown products")

    images = datasets["product_images"]
    unknown_image_products = {row["product_id"] for row in images} - product_ids
    if unknown_image_products:
        raise ValueError("product_images.csv references unknown products")
    unknown_image_variants = {
        row["variant_id"]
        for row in images
        if row["variant_id"] is not None
    } - variant_ids
    if unknown_image_variants:
        raise ValueError("product_images.csv references unknown variants")

    primary_counts = Counter(
        row["product_id"] for row in images if row["is_primary"] is True
    )
    invalid_primary = [
        product_id for product_id in product_ids if primary_counts[product_id] != 1
    ]
    if invalid_primary:
        raise ValueError("Every product must have exactly one primary image")


def validate_database_schema(connection: object) -> None:
    """Reject pre-existing tables whose columns are incompatible with the importer."""
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            ([spec.name for spec in TABLE_SPECS],),
        )
        rows = cursor.fetchall()
    actual: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        actual.setdefault(table_name, set()).add(column_name)
    for spec in TABLE_SPECS:
        missing = set(spec.columns) - actual.get(spec.name, set())
        if missing:
            raise RuntimeError(
                f"Existing public.{spec.name} is incompatible; missing columns: "
                + ", ".join(sorted(missing))
            )


def upsert_rows(
    connection: object,
    spec: TableSpec,
    rows: Sequence[dict[str, Any]],
    batch_size: int,
) -> None:
    """Upsert rows in bounded batches within the caller's transaction."""
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        for batch in _batches(rows, batch_size):
            cursor.executemany(spec.upsert_sql, batch)


def _convert_row(
    spec: TableSpec,
    row: dict[str, str],
    row_number: int,
) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for column in spec.columns:
        raw_value = row.get(column)
        if raw_value is None:
            raise ValueError(
                f"Missing column {column!r} in {spec.filename} row {row_number}"
            )
        value = raw_value.strip()
        if not value:
            if column in spec.nullable_columns:
                converted[column] = None
                continue
            raise ValueError(
                f"Blank required value {column!r} in {spec.filename} row {row_number}"
            )
        if column in spec.integer_columns:
            try:
                converted[column] = int(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid integer {column!r} in {spec.filename} row {row_number}"
                ) from exc
        elif column in spec.boolean_columns:
            if value.lower() not in {"true", "false"}:
                raise ValueError(
                    f"Invalid boolean {column!r} in {spec.filename} row {row_number}"
                )
            converted[column] = value.lower() == "true"
        else:
            converted[column] = value
    return converted


def _batches(
    rows: Sequence[dict[str, Any]], batch_size: int
) -> Iterable[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


if __name__ == "__main__":
    raise SystemExit(main())

