"""Tests for role schema planning, persistence mapping, and role operations."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.repositories.users import UserRepositoryError, _row_to_user
from scripts import create_auth_schema, manage_user_role, migrate_admin_catalog_schema


class FakeCursor:
    def __init__(self, responses: list[tuple[object, ...] | None]) -> None:
        self.responses = responses
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[object, ...] = ()) -> None:
        self.statements.append((statement, parameters))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.responses.pop(0)


class FakeConnection:
    def __init__(self, responses: list[tuple[object, ...] | None]) -> None:
        self.cursor_instance = FakeCursor(responses)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


def test_auth_role_migration_is_additive_and_idempotent() -> None:
    sql = create_auth_schema.MIGRATE_USER_ROLE_SQL.upper()

    assert "ADD COLUMN IF NOT EXISTS ROLE" in sql
    assert "UPDATE PUBLIC.USERS SET ROLE = 'CUSTOMER' WHERE ROLE IS NULL" in sql
    assert "USERS_ROLE_ALLOWED" in sql
    assert "USERS_ROLE_ACTIVE_IDX" in sql
    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql


def test_admin_catalog_migration_is_additive_and_idempotent() -> None:
    sql = migrate_admin_catalog_schema.MIGRATION_SQL.upper()

    assert "ADD COLUMN IF NOT EXISTS CREATED_BY" in sql
    assert "CREATE TABLE IF NOT EXISTS PUBLIC.ADMIN_AUDIT_EVENTS" in sql
    assert "CREATE TABLE IF NOT EXISTS PUBLIC.CATALOG_SYNC_JOBS" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql


def test_user_record_mapping_accepts_only_supported_roles() -> None:
    row = {
        "id": uuid4(),
        "email": "admin@example.com",
        "password_hash": "hidden",
        "is_active": True,
        "role": "admin",
        "created_at": datetime.now(timezone.utc),
    }

    assert _row_to_user(row).role == "admin"
    with pytest.raises(UserRepositoryError):
        _row_to_user({**row, "role": "super_admin"})


def test_manage_user_role_dry_run_normalizes_email_without_database(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = manage_user_role.main(
        ["--email", " Admin@Example.COM ", "--role", "admin"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"email": "admin@example.com"' in output
    assert '"requested_role": "admin"' in output


def test_manage_user_role_updates_only_the_selected_user() -> None:
    user_id = uuid4()
    connection = FakeConnection(
        [
            (user_id, "user@example.com", "customer", True),
            (user_id, "user@example.com", "admin", True),
        ]
    )

    result = manage_user_role._update_role(
        connection,
        email="user@example.com",
        role="admin",
    )

    assert result["action"] == "updated"
    assert result["previous_role"] == "customer"
    assert result["role"] == "admin"
    statements = connection.cursor_instance.statements
    assert statements[0][1] == ("user@example.com",)
    assert statements[1][1] == ("admin", user_id)
