"""Lazy PostgreSQL connection construction for Supabase."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when the direct PostgreSQL configuration is incomplete."""


class DatabaseConnectionError(RuntimeError):
    """Raised when PostgreSQL cannot be reached."""


def database_connection_kwargs(config: Settings) -> dict[str, Any]:
    """Build psycopg keyword arguments without interpolating a URL."""
    required = {
        "SUPABASE_DB_HOST": config.supabase_db_host,
        "SUPABASE_DB_USER": config.supabase_db_user,
        "SUPABASE_DB_PASSWORD": config.supabase_db_password,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise DatabaseConfigurationError(
            "Missing Supabase PostgreSQL settings: " + ", ".join(missing)
        )

    return {
        "host": config.supabase_db_host,
        "port": config.supabase_db_port,
        "dbname": config.supabase_db_name,
        "user": config.supabase_db_user,
        "password": config.supabase_db_password.get_secret_value(),
        "sslmode": config.supabase_db_ssl_mode,
        "connect_timeout": 10,
    }


def open_database_connection(config: Settings = settings) -> Any:
    """Open one request-scoped psycopg connection."""
    try:
        import psycopg
    except ImportError as exc:
        raise DatabaseConfigurationError(
            "PostgreSQL dependency is unavailable. Install requirements.txt."
        ) from exc

    try:
        return psycopg.connect(**database_connection_kwargs(config))
    except Exception as exc:
        raise DatabaseConnectionError(
            "Unable to connect to the configured Supabase PostgreSQL database"
        ) from exc
