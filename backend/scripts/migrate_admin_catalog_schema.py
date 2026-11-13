"""Preview or apply additive schema needed by admin catalog management."""

from __future__ import annotations

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
    "products": {"created_by", "updated_by", "version"},
    "product_images": {
        "index_status",
        "indexed_at",
        "index_error",
        "updated_at",
    },
    "admin_audit_events": {
        "id", "actor_user_id", "action", "resource_type", "resource_id",
        "before_data", "after_data", "request_id", "created_at",
    },
    "catalog_sync_jobs": {
        "id", "product_id", "image_id", "operation", "status", "attempts",
        "last_error", "next_attempt_at", "created_at", "updated_at",
    },
}

MIGRATION_SQL = """
ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE public.product_images ALTER COLUMN source_path DROP NOT NULL;
ALTER TABLE public.product_images
    ADD COLUMN IF NOT EXISTS index_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS indexed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS index_error TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.product_images'::regclass
          AND conname = 'product_images_index_status_allowed'
    ) THEN
        ALTER TABLE public.product_images
        ADD CONSTRAINT product_images_index_status_allowed
        CHECK (index_status IN ('pending', 'indexing', 'indexed', 'failed', 'removed'));
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.admin_audit_events (
    id UUID PRIMARY KEY,
    actor_user_id UUID NOT NULL REFERENCES public.users(id),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NOT NULL,
    before_data JSONB,
    after_data JSONB,
    request_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.catalog_sync_jobs (
    id UUID PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    image_id UUID REFERENCES public.product_images(id) ON DELETE CASCADE,
    operation TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT catalog_sync_jobs_operation_allowed
        CHECK (operation IN ('upsert_vector', 'update_metadata', 'delete_vector', 'delete_storage_object')),
    CONSTRAINT catalog_sync_jobs_status_allowed
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT catalog_sync_jobs_attempts_nonnegative CHECK (attempts >= 0)
);

CREATE INDEX IF NOT EXISTS products_admin_status_updated_idx
    ON public.products (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS products_admin_category_status_idx
    ON public.products (category_id, status);
CREATE INDEX IF NOT EXISTS product_images_index_status_idx
    ON public.product_images (index_status, updated_at);
CREATE INDEX IF NOT EXISTS admin_audit_resource_idx
    ON public.admin_audit_events (resource_type, resource_id, created_at DESC);
CREATE INDEX IF NOT EXISTS catalog_sync_jobs_pending_idx
    ON public.catalog_sync_jobs (status, next_attempt_at, created_at);
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add and validate admin catalog lifecycle schema."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the additive migration; otherwise print the plan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    plan = {
        "action": "plan",
        "tables": {name: sorted(columns) for name, columns in REQUIRED_COLUMNS.items()},
        "product_delete": "archive",
        "image_index_states": ["pending", "indexing", "indexed", "failed", "removed"],
    }
    if not args.apply:
        print(json.dumps(plan, indent=2))
        logger.info("Dry run only. Add --apply to migrate the admin catalog schema.")
        return 0

    try:
        connection = open_database_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(MIGRATION_SQL)
            connection.commit()
            _validate_schema(connection)
        finally:
            connection.close()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Admin catalog schema migration failed")
        return 1

    print(json.dumps({"action": "ready", "tables": list(REQUIRED_COLUMNS)}, indent=2))
    return 0


def _validate_schema(connection: object) -> None:
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
        cursor.execute(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_images'
              AND column_name = 'source_path'
            """
        )
        source_path = cursor.fetchone()

    actual = {name: set() for name in REQUIRED_COLUMNS}
    for table_name, column_name in rows:
        actual[table_name].add(column_name)
    missing = {
        name: sorted(columns - actual[name])
        for name, columns in REQUIRED_COLUMNS.items()
        if columns - actual[name]
    }
    if missing:
        raise RuntimeError(f"Admin catalog schema is missing columns: {missing}")
    if source_path is None or source_path[0] != "YES":
        raise RuntimeError("product_images.source_path must allow admin-uploaded images")


if __name__ == "__main__":
    raise SystemExit(main())
