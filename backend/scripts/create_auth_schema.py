"""Create and validate the minimal PostgreSQL schema for custom auth."""

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

REQUIRED_USER_COLUMNS = {
    "id",
    "email",
    "password_hash",
    "is_active",
    "role",
    "created_at",
}

CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    role TEXT NOT NULL DEFAULT 'customer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_email_lowercase CHECK (email = LOWER(email)),
    CONSTRAINT users_role_allowed CHECK (role IN ('customer', 'admin'))
);
"""

MIGRATE_USER_ROLE_SQL = """
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS role TEXT;
UPDATE public.users SET role = 'customer' WHERE role IS NULL;
ALTER TABLE public.users ALTER COLUMN role SET DEFAULT 'customer';
ALTER TABLE public.users ALTER COLUMN role SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.users'::regclass
          AND conname = 'users_role_allowed'
          AND contype = 'c'
    ) THEN
        ALTER TABLE public.users
        ADD CONSTRAINT users_role_allowed
        CHECK (role IN ('customer', 'admin'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS users_role_active_idx
    ON public.users (role, is_active);
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the idempotent public.users authentication schema."
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
        "table": "users",
        "columns": sorted(REQUIRED_USER_COLUMNS),
        "unique": ["email"],
        "roles": ["customer", "admin"],
        "existing_user_backfill": "customer",
    }
    if not args.apply:
        print(json.dumps(plan, indent=2))
        logger.info("Dry run only. Add --apply to create the auth schema.")
        return 0

    try:
        connection = open_database_connection()
        try:
            existed = _users_table_exists(connection)
            with connection.cursor() as cursor:
                cursor.execute(CREATE_USERS_SQL)
                cursor.execute(MIGRATE_USER_ROLE_SQL)
                _ensure_email_unique_index(cursor)
            connection.commit()
            _validate_users_columns(connection)
            _validate_user_role_schema(connection)
        finally:
            connection.close()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Auth schema creation failed")
        return 1

    print(
        json.dumps(
            {
                "action": "existing" if existed else "created",
                "schema": "public",
                "table": "users",
            },
            indent=2,
        )
    )
    return 0


def _users_table_exists(connection: object) -> bool:
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute("SELECT to_regclass('public.users')")
        row = cursor.fetchone()
    return bool(row and row[0])


def _validate_users_columns(connection: object) -> None:
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            """
        )
        actual_columns = {row[0] for row in cursor.fetchall()}
    missing = sorted(REQUIRED_USER_COLUMNS - actual_columns)
    if missing:
        raise RuntimeError(
            "Existing public.users table is incompatible; missing columns: "
            + ", ".join(missing)
        )


def _ensure_email_unique_index(cursor: object) -> None:
    """Create email uniqueness only when no equivalent unique index exists."""
    cursor.execute(  # type: ignore[attr-defined]
        """
        SELECT 1
        FROM pg_index i
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND t.relname = 'users'
          AND i.indisunique
          AND i.indpred IS NULL
          AND i.indexprs IS NULL
          AND i.indnkeyatts = 1
          AND (
              SELECT a.attname
              FROM pg_attribute a
              WHERE a.attrelid = t.oid AND a.attnum = i.indkey[0]
          ) = 'email'
        LIMIT 1
        """
    )
    if cursor.fetchone() is None:  # type: ignore[attr-defined]
        cursor.execute(  # type: ignore[attr-defined]
            "CREATE UNIQUE INDEX users_email_unique_idx ON public.users (email)"
        )


def _validate_user_role_schema(connection: object) -> None:
    """Verify role invariants after creating or migrating public.users."""
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            SELECT is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'role'
            """
        )
        column = cursor.fetchone()
        if column is None or column[0] != "NO" or "customer" not in str(column[1]):
            raise RuntimeError(
                "public.users.role must be NOT NULL with default 'customer'"
            )

        cursor.execute(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'public.users'::regclass
              AND conname = 'users_role_allowed'
              AND contype = 'c'
            """
        )
        constraint = cursor.fetchone()
        definition = str(constraint[0]) if constraint else ""
        if "role" not in definition or "customer" not in definition or "admin" not in definition:
            raise RuntimeError("public.users role constraint is missing or incompatible")

        cursor.execute(
            "SELECT COUNT(*) FROM public.users WHERE role NOT IN ('customer', 'admin')"
        )
        invalid_count = int(cursor.fetchone()[0])
        if invalid_count:
            raise RuntimeError("public.users contains unsupported role values")


if __name__ == "__main__":
    raise SystemExit(main())
