"""Environment-backed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Image-Based Product Search API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    model_path: str = "artifacts/alexnet.pth"

    classifier_artifact_root: Path = Path("artifacts/classifiers")
    classifier_device: Literal["auto", "cpu", "cuda"] = "auto"
    classifier_default_model: Literal["none", "alexnet", "resnet50", "vit"] = "none"
    classifier_top_k: int = Field(default=5, gt=0, le=42)
    classifier_max_top_k: int = Field(default=10, gt=0, le=42)

    pinecone_api_key: SecretStr | None = None
    pinecone_index_name: str | None = None
    pinecone_namespace: str | None = None
    pinecone_vector_field: str | None = None
    pinecone_dimension: int | None = Field(default=None, gt=0)
    pinecone_metric: Literal["cosine", "euclidean", "dotproduct"] | None = None
    pinecone_cloud: str | None = None
    pinecone_region: str | None = None
    pinecone_deletion_protection: Literal["enabled", "disabled"] = "enabled"
    pinecone_create_timeout: int = Field(default=300, gt=0)

    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"
    clip_device: Literal["auto", "cpu", "cuda"] = "auto"
    clip_cache_dir: Path | None = None

    ingest_dataset_path: Path | None = None
    ingest_batch_size: int = Field(default=64, gt=0)
    search_test_dataset_path: Path | None = None

    supabase_db_host: str | None = None
    supabase_db_port: int = 5432
    supabase_db_name: str = "postgres"
    supabase_db_user: str | None = None
    supabase_db_password: SecretStr | None = None
    supabase_db_ssl_mode: Literal[
        "disable",
        "allow",
        "prefer",
        "require",
        "verify-ca",
        "verify-full",
    ] = "require"

    # Supabase HTTP API/Storage settings are separate from the direct DB fields.
    supabase_url: str | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_storage_bucket: str | None = None
    supabase_storage_bucket_public: bool = False
    supabase_storage_upload_workers: int = Field(default=4, gt=0, le=16)
    supabase_storage_timeout_seconds: float = Field(default=60.0, gt=0)
    supabase_storage_signed_url_ttl_seconds: int = Field(
        default=3600,
        gt=0,
        le=86400,
    )
    supabase_storage_max_standard_upload_bytes: int = Field(
        default=6 * 1024 * 1024,
        gt=0,
    )

    jwt_secret: SecretStr | None = None
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0)
    jwt_issuer: str = "image-search-api"
    jwt_audience: str = "image-search-web"

    image_upload_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    image_upload_max_pixels: int = Field(default=25_000_000, gt=0)
    image_search_default_limit: int = Field(default=50, gt=0, le=100)
    image_search_max_limit: int = Field(default=50, gt=0, le=100)
    image_search_top_k: int = Field(default=50, gt=0, le=100)


@lru_cache
def get_settings() -> Settings:
    """Return the single process-wide settings instance."""
    return Settings()


settings = get_settings()
