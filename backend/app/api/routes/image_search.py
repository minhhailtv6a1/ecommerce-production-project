"""Public CLIP visual product-search endpoint."""

from __future__ import annotations

from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.datastructures import UploadFile

from app.api.dependencies import get_image_search_resources, get_product_service
from app.core.config import settings
from app.schemas.image_search import ImageSearchResponse
from app.services.image_search import QueryImageError, search_similar_image_bytes
from app.services.image_upload import (
    InvalidUploadedImageError,
    validate_uploaded_image,
)
from app.services.product_service import ProductService
from app.services.storage_upload import StorageUploadError
from app.services.visual_search import hydrate_visual_search_matches


router = APIRouter(prefix="/image-search", tags=["image-search"])


@router.post(
    "/search",
    response_model=ImageSearchResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["image"],
                        "properties": {
                            "image": {"type": "string", "format": "binary"},
                            "category_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "limit": {"type": "integer", "minimum": 1},
                        },
                    }
                }
            },
        }
    },
)
async def search_products_by_image(
    request: Request,
    product_service: Annotated[ProductService, Depends(get_product_service)],
) -> ImageSearchResponse:
    """Validate/embed an image, retrieve vectors, and hydrate public products."""
    try:
        form = await request.form(
            max_files=1,
            max_fields=60,
            max_part_size=settings.image_upload_max_bytes + 1,
        )
    except (AssertionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Multipart upload support is unavailable",
        ) from exc
    image = form.get("image")
    if not isinstance(image, UploadFile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="image is required",
        )
    category_ids = [str(value) for value in form.getlist("category_ids")]
    raw_limit = form.get("limit")
    try:
        requested_limit = (
            int(str(raw_limit))
            if raw_limit not in {None, ""}
            else settings.image_search_default_limit
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="limit must be an integer",
        ) from exc
    if requested_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="limit must be positive",
        )
    if requested_limit > settings.image_search_max_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"limit must not exceed {settings.image_search_max_limit}",
        )
    content = await image.read(settings.image_upload_max_bytes + 1)
    await image.close()
    try:
        validate_uploaded_image(
            content,
            content_type=image.content_type,
            max_bytes=settings.image_upload_max_bytes,
            max_pixels=settings.image_upload_max_pixels,
        )
    except InvalidUploadedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    try:
        retrieval_started_at = perf_counter()
        embedder, searcher, vector_field = get_image_search_resources()
        matches = search_similar_image_bytes(
            content=content,
            embedder=embedder,
            searcher=searcher,
            vector_field=vector_field,
            top_k=settings.image_search_top_k,
            category_ids=category_ids or (),
        )
        search_response = hydrate_visual_search_matches(
            matches,
            product_service=product_service,
            limit=requested_limit,
        )
        retrieval_time_ms = round(
            (perf_counter() - retrieval_started_at) * 1000,
            2,
        )
        return ImageSearchResponse(
            items=search_response.items,
            retrieval_time_ms=retrieval_time_ms,
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
