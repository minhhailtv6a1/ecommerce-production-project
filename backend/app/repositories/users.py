"""PostgreSQL persistence for application-owned users."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID, uuid4


class UserAlreadyExistsError(RuntimeError):
    """Raised when a normalized email already exists."""


class UserRepositoryError(RuntimeError):
    """Raised when PostgreSQL user persistence fails."""


@dataclass(frozen=True)
class UserRecord:
    """User data used by authentication business logic."""

    id: UUID
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime


class PostgresUserRepository:
    """Store and retrieve users using parameterized PostgreSQL statements."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def get_by_email(self, email: str) -> UserRecord | None:
        try:
            row = self._fetch_one(
                """
                SELECT id, email, password_hash, is_active, created_at
                FROM public.users
                WHERE email = %s
                """,
                (email,),
            )
        except Exception as exc:
            raise UserRepositoryError("Unable to read users from PostgreSQL") from exc
        return _row_to_user(row) if row is not None else None

    def get_by_id(self, user_id: UUID) -> UserRecord | None:
        try:
            row = self._fetch_one(
                """
                SELECT id, email, password_hash, is_active, created_at
                FROM public.users
                WHERE id = %s
                """,
                (user_id,),
            )
        except Exception as exc:
            raise UserRepositoryError("Unable to read users from PostgreSQL") from exc
        return _row_to_user(row) if row is not None else None

    def create(self, *, email: str, password_hash: str) -> UserRecord:
        try:
            row = self._fetch_one(
                """
                INSERT INTO public.users (id, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, email, password_hash, is_active, created_at
                """,
                (uuid4(), email, password_hash),
            )
            self._connection.commit()
        except Exception as exc:
            self._connection.rollback()
            if getattr(exc, "sqlstate", None) == "23505":
                raise UserAlreadyExistsError from exc
            raise UserRepositoryError("Unable to create user in PostgreSQL") from exc

        if row is None:
            raise RuntimeError("PostgreSQL did not return the created user")
        return _row_to_user(row)

    def _fetch_one(
        self,
        statement: str,
        parameters: tuple[Any, ...],
    ) -> Mapping[str, Any] | None:
        try:
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL dependency is unavailable. Install requirements.txt."
            ) from exc

        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchone()


def _row_to_user(row: Mapping[str, Any]) -> UserRecord:
    return UserRecord(
        id=UUID(str(row["id"])),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )
