"""Public product-category endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_product_repository
from app.repositories.products import ProductRepository
from app.schemas.catalog import CategoryListResponse


router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
def list_categories(
    repository: Annotated[ProductRepository, Depends(get_product_repository)],
) -> CategoryListResponse:
    """List active storefront categories and their published product count."""
    return CategoryListResponse(items=repository.list_categories())
