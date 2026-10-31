"""Request-scoped application dependencies."""

from collections.abc import Iterator
from functools import lru_cache

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.repositories.database import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    open_database_connection,
)
from app.repositories.products import ProductRepository
from app.repositories.commerce import CommerceRepository
from app.repositories.pinecone import (
    PineconeDocumentRepository,
    PineconeSdkUnavailableError,
    create_pinecone_client,
)
from app.services.image_ingestion import (
    ImageEmbeddingDependencyError,
    OpenClipImageEmbedder,
)
from app.classifiers.registry import ClassifierRegistry
from app.services.image_classification import ImageClassificationService
from app.services.pinecone_index import (
    PineconeIndexConfigurationError,
    PineconeIndexMismatchError,
    PineconeIndexNotFoundError,
    index_definition_from_settings,
    validate_pinecone_index,
)
from app.services.product_service import ProductService
from app.services.commerce import CommerceService
from app.services.storage_upload import SupabaseStorageUrlResolver


def get_product_service() -> Iterator[ProductService]:
    """Provide one DB connection and Storage HTTP client per request."""
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SECRET_KEY": settings.supabase_secret_key,
        "SUPABASE_STORAGE_BUCKET": settings.supabase_storage_bucket,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product image storage is not configured",
        )
    try:
        connection = open_database_connection()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product catalog is unavailable",
        ) from exc

    client = httpx.Client(timeout=settings.supabase_storage_timeout_seconds)
    try:
        resolver = SupabaseStorageUrlResolver(
            supabase_url=settings.supabase_url or "",
            secret_key=settings.supabase_secret_key.get_secret_value(),
            bucket=settings.supabase_storage_bucket or "",
            bucket_public=settings.supabase_storage_bucket_public,
            signed_url_ttl_seconds=(
                settings.supabase_storage_signed_url_ttl_seconds
            ),
            client=client,
        )
        yield ProductService(ProductRepository(connection), resolver)
    finally:
        client.close()
        connection.close()


def get_product_repository() -> Iterator[ProductRepository]:
    """Provide catalog reads that do not require product image URL signing."""
    try:
        connection = open_database_connection()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product catalog is unavailable",
        ) from exc
    try:
        yield ProductRepository(connection)
    finally:
        connection.close()


def get_commerce_service() -> Iterator[CommerceService]:
    """Provide a request-scoped transactional cart/order service."""
    try:
        connection = open_database_connection()
    except (DatabaseConfigurationError, DatabaseConnectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cart and order database is unavailable",
        ) from exc
    try:
        yield CommerceService(CommerceRepository(connection))
    finally:
        connection.close()


@lru_cache
def get_image_search_resources() -> tuple[
    OpenClipImageEmbedder,
    PineconeDocumentRepository,
    str,
]:
    """Lazily initialize and reuse CLIP plus the Pinecone index client."""
    if settings.pinecone_api_key is None or not settings.pinecone_namespace:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image search is not configured",
        )
    try:
        definition = index_definition_from_settings(settings)
        client = create_pinecone_client(
            settings.pinecone_api_key.get_secret_value()
        )
        index_status = validate_pinecone_index(client, definition)
        if not index_status.ready:
            raise RuntimeError("Pinecone index is not ready")
        repository = PineconeDocumentRepository(
            client.index(definition.name),
            settings.pinecone_namespace,
        )
        embedder = OpenClipImageEmbedder(
            model_name=settings.clip_model_name,
            pretrained=settings.clip_pretrained,
            expected_dimension=definition.dimension,
            device=settings.clip_device,
            cache_dir=settings.clip_cache_dir,
        )
        return embedder, repository, definition.vector_field
    except (
        ImageEmbeddingDependencyError,
        PineconeIndexConfigurationError,
        PineconeIndexMismatchError,
        PineconeIndexNotFoundError,
        PineconeSdkUnavailableError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image search is unavailable",
        ) from exc


@lru_cache
def get_classifier_registry() -> ClassifierRegistry:
    """Discover classifier artifacts once and lazily load their models."""
    return ClassifierRegistry(
        settings.classifier_artifact_root,
        device=settings.classifier_device,
    )


@lru_cache
def get_classification_service() -> ImageClassificationService:
    """Reuse the classifier registry across classification requests."""
    return ImageClassificationService(get_classifier_registry())
