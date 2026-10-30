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
    "created_at",
}

CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_email_lowercase CHECK (email = LOWER(email))
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx
    ON public.users (email);
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
            connection.commit()
            _validate_users_columns(connection)
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


if __name__ == "__main__":
    raise SystemExit(main())
