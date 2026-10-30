"""Tests for direct Supabase PostgreSQL connection configuration."""

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.repositories.database import (
    DatabaseConfigurationError,
    database_connection_kwargs,
)


def test_database_kwargs_preserve_separate_connection_fields() -> None:
    config = Settings(
        _env_file=None,
        supabase_db_host="db.example.supabase.co",
        supabase_db_port=5432,
        supabase_db_name="postgres",
        supabase_db_user="postgres",
        supabase_db_password=SecretStr("database-secret"),
        supabase_db_ssl_mode="require",
    )

    kwargs = database_connection_kwargs(config)

    assert kwargs == {
        "host": "db.example.supabase.co",
        "port": 5432,
        "dbname": "postgres",
        "user": "postgres",
        "password": "database-secret",
        "sslmode": "require",
        "connect_timeout": 10,
    }


def test_database_config_rejects_missing_credentials() -> None:
    config = Settings(_env_file=None)

    with pytest.raises(DatabaseConfigurationError, match="SUPABASE_DB_HOST"):
        database_connection_kwargs(config)
