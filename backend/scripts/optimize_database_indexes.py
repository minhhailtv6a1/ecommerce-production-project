"""Safely remove application indexes proven redundant by equivalent keys."""

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
REDUNDANT_INDEXES = {
    "public.idx_users_email": {
        "required_fragment": "USING btree (email)",
        "replacement": "public.users_email_key",
    },
    "public.cart_items_user_idx": {
        "required_fragment": "USING btree (user_id)",
        "replacement": "public.cart_items_pkey",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and optionally remove known redundant indexes."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Drop only validated redundant indexes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    plan = [
        {"index": name, "replacement": config["replacement"]}
        for name, config in REDUNDANT_INDEXES.items()
    ]
    if not args.apply:
        print(json.dumps({"action": "plan", "drops": plan}, indent=2))
        logger.info("Dry run only. Add --apply after reviewing the exact targets.")
        return 0

    try:
        connection = open_database_connection()
        connection.autocommit = True
        try:
            results = [
                _drop_validated(connection, name, config)
                for name, config in REDUNDANT_INDEXES.items()
            ]
        finally:
            connection.close()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Index optimization failed")
        return 1

    print(json.dumps({"action": "applied", "results": results}, indent=2))
    return 0


def _drop_validated(
    connection: object,
    name: str,
    config: dict[str, str],
) -> dict[str, str]:
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            SELECT i.indisprimary, c.conname, pg_get_indexdef(i.indexrelid)
            FROM pg_index i
            LEFT JOIN pg_constraint c ON c.conindid = i.indexrelid
            WHERE i.indexrelid = to_regclass(%s)
            """,
            (name,),
        )
        row = cursor.fetchone()
        if row is None:
            return {"index": name, "status": "already_absent"}
        is_primary, constraint_name, definition = row
        if is_primary or constraint_name or config["required_fragment"] not in definition:
            raise RuntimeError(f"Refusing to drop unexpected index definition: {name}")
        cursor.execute(f"DROP INDEX CONCURRENTLY {name}")
    return {"index": name, "status": "dropped"}


if __name__ == "__main__":
    raise SystemExit(main())
