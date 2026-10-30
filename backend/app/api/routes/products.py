"""Public catalog and product-detail endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_product_service
from app.repositories.products import ProductFilters
from app.schemas.catalog import ProductDetailResponse, ProductListResponse
from app.services.image_search import QueryImageError, normalize_category_ids
from app.services.product_service import ProductNotFoundError, ProductService
from app.services.storage_upload import StorageUploadError


router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    service: Annotated[ProductService, Depends(get_product_service)],
    category_ids: Annotated[list[str] | None, Query()] = None,
    size: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    in_stock: bool | None = None,
    sort: Literal["newest", "price_asc", "price_desc"] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductListResponse:
    """List published products with supported variant filters and pagination."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="min_price must not exceed max_price",
        )
    try:
        normalized_categories = normalize_category_ids(category_ids or ())
        return service.list_products(
            ProductFilters(
                category_ids=normalized_categories,
                size=size,
                color=color,
                brand=brand,
                min_price=min_price,
                max_price=max_price,
                in_stock=in_stock,
                sort=sort,
                page=page,
                page_size=limit,
            )
        )
    except QueryImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except StorageUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product images are temporarily unavailable",
        ) from exc


@router.get("/{identifier}", response_model=ProductDetailResponse)
def get_product(
    identifier: str,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductDetailResponse:
    """Return one published product by UUID or slug, including real variants."""
    try:
        return service.product_detail(identifier)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        ) from exc
    except StorageUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product images are temporarily unavailable",
        ) from exc
