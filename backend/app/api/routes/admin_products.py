"""Admin-only product, variant, image, and lifecycle endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from starlette.datastructures import UploadFile

from app.api.dependencies import get_admin_catalog_service
from app.api.routes.auth import require_admin
from app.core.config import settings
from app.repositories.admin_products import (
    AdminCatalogConflictError,
    AdminCatalogRepositoryError,
    AdminProductNotFoundError,
    AdminProductVersionConflictError,
)
from app.repositories.users import UserRecord
from app.schemas.admin_catalog import (
    AdminImageResponse,
    AdminImageUpdateRequest,
    AdminProductCreateRequest,
    AdminProductListResponse,
    AdminProductResponse,
    AdminProductUpdateRequest,
    AdminVariantCreateRequest,
    AdminVariantResponse,
    AdminVariantUpdateRequest,
    ImageIndexStatus,
    ProductStatus,
)
from app.services.admin_catalog import AdminCatalogService, AdminProductNotPublishableError
from app.services.catalog_indexing import CatalogIndexingError
from app.services.image_upload import InvalidUploadedImageError, validate_uploaded_image
from app.services.storage_upload import StorageManifestError, StorageUploadError


router = APIRouter(prefix="/admin/products", tags=["admin-products"])
T = TypeVar("T")


@router.get("", response_model=AdminProductListResponse)
def list_admin_products(
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
    keyword: str | None = Query(default=None, max_length=240),
    category_id: str | None = Query(default=None, pattern=r"^[0-9]{2}$"),
    product_status: ProductStatus | None = Query(default=None, alias="status"),
    index_status: ImageIndexStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> AdminProductListResponse:
    del admin
    return AdminProductListResponse.model_validate(
        _run(
            lambda: service.list_products(
                keyword=keyword.strip() if keyword else None,
                category_id=category_id,
                status=product_status,
                index_status=index_status,
                page=page,
                page_size=limit,
            )
        )
    )


@router.get("/{product_id}", response_model=AdminProductResponse)
def get_admin_product(
    product_id: UUID,
    _admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    return AdminProductResponse.model_validate(_run(lambda: service.get_product(product_id)))


@router.post("", response_model=AdminProductResponse, status_code=status.HTTP_201_CREATED)
def create_admin_product(
    payload: AdminProductCreateRequest,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    result = _run(
        lambda: service.create_product(
            actor_id=admin.id,
            values=payload.model_dump(),
            request_id=_request_id(request),
        )
    )
    return AdminProductResponse.model_validate(result)


@router.patch("/{product_id}", response_model=AdminProductResponse)
def update_admin_product(
    product_id: UUID,
    payload: AdminProductUpdateRequest,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    values = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    result = _run(
        lambda: service.update_product(
            product_id=product_id,
            actor_id=admin.id,
            expected_version=payload.expected_version,
            values=values,
            request_id=_request_id(request),
        )
    )
    return AdminProductResponse.model_validate(result)


@router.delete("/{product_id}", response_model=AdminProductResponse)
def archive_admin_product(
    product_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    return AdminProductResponse.model_validate(
        _run(
            lambda: service.archive(
                product_id=product_id,
                actor_id=admin.id,
                request_id=_request_id(request),
            )
        )
    )


@router.post("/{product_id}/restore", response_model=AdminProductResponse)
def restore_admin_product(
    product_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    return AdminProductResponse.model_validate(
        _run(
            lambda: service.restore(
                product_id=product_id,
                actor_id=admin.id,
                request_id=_request_id(request),
            )
        )
    )


@router.post("/{product_id}/publish", response_model=AdminProductResponse)
def publish_admin_product(
    product_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    return AdminProductResponse.model_validate(
        _run(
            lambda: service.publish(
                product_id=product_id,
                actor_id=admin.id,
                request_id=_request_id(request),
            )
        )
    )


@router.post("/{product_id}/index", response_model=AdminProductResponse)
def index_admin_product(
    product_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminProductResponse:
    return AdminProductResponse.model_validate(
        _run(
            lambda: service.index_product(
                product_id=product_id,
                actor_id=admin.id,
                request_id=_request_id(request),
            )
        )
    )


@router.post(
    "/{product_id}/variants",
    response_model=AdminVariantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_variant(
    product_id: UUID,
    payload: AdminVariantCreateRequest,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminVariantResponse:
    return AdminVariantResponse.model_validate(
        _run(
            lambda: service.add_variant(
                product_id=product_id,
                actor_id=admin.id,
                values=payload.model_dump(),
                request_id=_request_id(request),
            )
        )
    )


@router.patch("/{product_id}/variants/{variant_id}", response_model=AdminVariantResponse)
def update_admin_variant(
    product_id: UUID,
    variant_id: UUID,
    payload: AdminVariantUpdateRequest,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminVariantResponse:
    return AdminVariantResponse.model_validate(
        _run(
            lambda: service.update_variant(
                product_id=product_id,
                variant_id=variant_id,
                actor_id=admin.id,
                values=payload.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
        )
    )


@router.delete("/{product_id}/variants/{variant_id}", response_model=AdminVariantResponse)
def deactivate_admin_variant(
    product_id: UUID,
    variant_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminVariantResponse:
    return AdminVariantResponse.model_validate(
        _run(
            lambda: service.deactivate_variant(
                product_id=product_id,
                variant_id=variant_id,
                actor_id=admin.id,
                request_id=_request_id(request),
            )
        )
    )


@router.post(
    "/{product_id}/images",
    response_model=AdminImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_admin_image(
    product_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminImageResponse:
    try:
        form = await request.form(
            max_files=1,
            max_fields=5,
            max_part_size=settings.image_upload_max_bytes + 1,
        )
    except (AssertionError, RuntimeError) as exc:
        raise _error(503, "SERVICE_UNAVAILABLE", "Multipart upload support is unavailable") from exc
    image = form.get("image")
    if not isinstance(image, UploadFile):
        raise _error(422, "IMAGE_INVALID", "image is required")
    content = await image.read(settings.image_upload_max_bytes + 1)
    await image.close()
    try:
        suffix = validate_uploaded_image(
            content,
            content_type=image.content_type,
            max_bytes=settings.image_upload_max_bytes,
            max_pixels=settings.image_upload_max_pixels,
        )
        sort_order = int(str(form.get("sort_order") or "0"))
        if sort_order < 0 or sort_order > 32_767:
            raise ValueError
        is_primary = _parse_bool(form.get("is_primary"), default=False)
        alt_text = str(form.get("alt_text") or "").strip()
        if not alt_text or len(alt_text) > 500:
            raise _error(422, "VALIDATION_ERROR", "alt_text is required and must not exceed 500 characters")
    except InvalidUploadedImageError as exc:
        raise _error(422, "IMAGE_INVALID", str(exc)) from exc
    except ValueError as exc:
        raise _error(422, "VALIDATION_ERROR", "Invalid image metadata") from exc

    result = _run(
        lambda: service.upload_image(
            product_id=product_id,
            actor_id=admin.id,
            content=content,
            content_type=image.content_type or "application/octet-stream",
            suffix=suffix,
            alt_text=alt_text,
            sort_order=sort_order,
            is_primary=is_primary,
            request_id=_request_id(request),
        )
    )
    return AdminImageResponse.model_validate(result)


@router.patch("/{product_id}/images/{image_id}", response_model=AdminImageResponse)
def update_admin_image(
    product_id: UUID,
    image_id: UUID,
    payload: AdminImageUpdateRequest,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> AdminImageResponse:
    return AdminImageResponse.model_validate(
        _run(
            lambda: service.update_image(
                product_id=product_id,
                image_id=image_id,
                actor_id=admin.id,
                values=payload.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
        )
    )


@router.delete(
    "/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_admin_image(
    product_id: UUID,
    image_id: UUID,
    request: Request,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[AdminCatalogService, Depends(get_admin_catalog_service)],
) -> Response:
    _run(
        lambda: service.remove_image(
            product_id=product_id,
            image_id=image_id,
            actor_id=admin.id,
            request_id=_request_id(request),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _run(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except AdminProductNotFoundError as exc:
        raise _error(404, "PRODUCT_NOT_FOUND", "Product or child resource was not found") from exc
    except AdminProductVersionConflictError as exc:
        raise _error(409, "PRODUCT_VERSION_CONFLICT", str(exc)) from exc
    except AdminProductNotPublishableError as exc:
        raise _error(409, "PRODUCT_NOT_PUBLISHABLE", "; ".join(exc.reasons)) from exc
    except AdminCatalogConflictError as exc:
        raise _error(409, "CATALOG_CONFLICT", str(exc)) from exc
    except (InvalidUploadedImageError, StorageManifestError) as exc:
        raise _error(422, "IMAGE_INVALID", str(exc)) from exc
    except StorageUploadError as exc:
        raise _error(503, "IMAGE_STORAGE_FAILED", "Product image storage failed") from exc
    except CatalogIndexingError as exc:
        raise _error(503, "VECTOR_INDEX_FAILED", str(exc)) from exc
    except AdminCatalogRepositoryError as exc:
        raise _error(503, "SERVICE_UNAVAILABLE", "Admin catalog database is unavailable") from exc


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _parse_bool(value: object, *, default: bool) -> bool:
    if value in {None, ""}:
        return default
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Invalid boolean")


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
