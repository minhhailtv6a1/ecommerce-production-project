"""Preview or apply an explicit customer/admin role change by normalized email."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from typing import Literal

from app.repositories.database import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    open_database_connection,
)


logger = logging.getLogger(__name__)
UserRole = Literal["customer", "admin"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or apply an application user role change."
    )
    parser.add_argument("--email", required=True, help="Existing normalized user email.")
    parser.add_argument(
        "--role",
        required=True,
        choices=("customer", "admin"),
        help="Role to assign.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the role change. Without this flag, only print the plan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        email = _normalize_email(args.email)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    plan = {
        "action": "plan",
        "email": email,
        "requested_role": args.role,
    }
    if not args.apply:
        print(json.dumps(plan, indent=2))
        logger.info("Dry run only. Add --apply to update the user role.")
        return 0

    try:
        connection = open_database_connection()
        try:
            result = _update_role(connection, email=email, role=args.role)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        logger.error("%s", exc)
        return 2
    except LookupError as exc:
        logger.error("%s", exc)
        return 3
    except Exception:
        logger.exception("User role update failed")
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


def _normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if (
        len(email) > 320
        or email.count("@") != 1
        or any(character.isspace() for character in email)
    ):
        raise ValueError("Invalid email address")
    local_part, domain = email.split("@")
    if not local_part or not domain or "." not in domain:
        raise ValueError("Invalid email address")
    return email


def _update_role(connection: object, *, email: str, role: UserRole) -> dict[str, object]:
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            SELECT id, email, role, is_active
            FROM public.users
            WHERE email = %s
            FOR UPDATE
            """,
            (email,),
        )
        current = cursor.fetchone()
        if current is None:
            raise LookupError(f"No application user found for {email}")

        previous_role = str(current[2])
        if previous_role != role:
            cursor.execute(
                """
                UPDATE public.users
                SET role = %s
                WHERE id = %s
                RETURNING id, email, role, is_active
                """,
                (role, current[0]),
            )
            updated = cursor.fetchone()
            if updated is None:
                raise RuntimeError("PostgreSQL did not return the updated user")
        else:
            updated = current

    return {
        "action": "unchanged" if previous_role == role else "updated",
        "user_id": updated[0],
        "email": updated[1],
        "previous_role": previous_role,
        "role": updated[2],
        "is_active": bool(updated[3]),
    }


if __name__ == "__main__":
    raise SystemExit(main())
