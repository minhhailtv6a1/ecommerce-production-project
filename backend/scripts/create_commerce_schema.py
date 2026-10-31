"""Create and validate the minimal PostgreSQL cart/order schema."""

import argparse
import json
import logging
from collections.abc import Sequence

from app.repositories.database import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    open_database_connection,
)


logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "cart_items": {"user_id", "variant_id", "quantity", "created_at", "updated_at"},
    "orders": {
        "id", "user_id", "status", "payment_method", "receiver_name", "phone",
        "shipping_address", "note", "total_amount", "currency", "created_at",
        "updated_at",
    },
    "order_items": {
        "id", "order_id", "product_id", "variant_id", "product_name", "sku",
        "color", "size", "unit_price", "quantity", "line_total", "created_at",
    },
}

CREATE_COMMERCE_SQL = """
CREATE TABLE IF NOT EXISTS public.cart_items (
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES public.product_variants(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, variant_id),
    CONSTRAINT cart_items_quantity_positive CHECK (quantity > 0 AND quantity <= 99)
);

CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'pending',
    payment_method TEXT NOT NULL DEFAULT 'cod',
    receiver_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    shipping_address VARCHAR(500) NOT NULL,
    note VARCHAR(500),
    total_amount BIGINT NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT orders_status_allowed
        CHECK (status IN ('pending', 'confirmed', 'shipping', 'completed', 'cancelled')),
    CONSTRAINT orders_payment_method_allowed CHECK (payment_method = 'cod'),
    CONSTRAINT orders_total_nonnegative CHECK (total_amount >= 0),
    CONSTRAINT orders_currency_format CHECK (currency ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS public.order_items (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    variant_id UUID NOT NULL REFERENCES public.product_variants(id) ON DELETE RESTRICT,
    product_name TEXT NOT NULL,
    sku TEXT NOT NULL,
    color TEXT,
    size TEXT,
    unit_price BIGINT NOT NULL,
    quantity INTEGER NOT NULL,
    line_total BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_items_price_nonnegative CHECK (unit_price >= 0),
    CONSTRAINT order_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT order_items_total_valid CHECK (line_total = unit_price * quantity)
);

CREATE INDEX IF NOT EXISTS orders_user_created_idx
    ON public.orders (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS order_items_order_idx ON public.order_items (order_id);
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the idempotent cart and order schema."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Connect to PostgreSQL and create/validate the schema.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    plan = {
        "action": "plan",
        "schema": "public",
        "tables": {name: sorted(columns) for name, columns in REQUIRED_COLUMNS.items()},
    }
    if not args.apply:
        print(json.dumps(plan, indent=2))
        logger.info("Dry run only. Add --apply to create the commerce schema.")
        return 0

    try:
        connection = open_database_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(CREATE_COMMERCE_SQL)
            connection.commit()
            _validate_columns(connection)
        finally:
            connection.close()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Commerce schema creation failed")
        return 1

    print(json.dumps({"action": "ready", "schema": "public", "tables": list(REQUIRED_COLUMNS)}, indent=2))
    return 0


def _validate_columns(connection: object) -> None:
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ANY(%s)
            """,
            (list(REQUIRED_COLUMNS),),
        )
        rows = cursor.fetchall()
    actual = {name: set() for name in REQUIRED_COLUMNS}
    for table_name, column_name in rows:
        actual[table_name].add(column_name)
    errors = [
        f"{name}: {', '.join(sorted(columns - actual[name]))}"
        for name, columns in REQUIRED_COLUMNS.items()
        if columns - actual[name]
    ]
    if errors:
        raise RuntimeError("Commerce schema is incompatible; missing " + "; ".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())
