"""Classifier capability and image-classification endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.datastructures import UploadFile

from app.api.dependencies import (
    get_classification_service,
    get_classifier_registry,
)
from app.classifiers.base import (
    ClassificationInferenceError,
    ClassifierLoadError,
    ClassifierUnavailableError,
    UnknownClassifierError,
)
from app.classifiers.registry import ClassifierRegistry
from app.core.config import settings
from app.schemas.image_classification import (
    ClassificationModelResponse,
    ClassificationPredictionResponse,
    ClassificationTimingResponse,
    ClassifierCapabilityResponse,
    ClassifierListResponse,
    ImageClassificationResponse,
)
from app.services.image_classification import ImageClassificationService
from app.services.image_upload import InvalidUploadedImageError, validate_uploaded_image


router = APIRouter(prefix="/image-search", tags=["image-classification"])


@router.get("/classifiers", response_model=ClassifierListResponse)
def list_classifiers(
    registry: Annotated[ClassifierRegistry, Depends(get_classifier_registry)],
) -> ClassifierListResponse:
    return ClassifierListResponse(
        items=[
            ClassifierCapabilityResponse(
                id=item.id,  # type: ignore[arg-type]
                display_name=item.display_name,
                available=item.available,
                version=item.version,
                input_size=item.input_size,
            )
            for item in registry.capabilities()
        ]
    )


@router.post("/classify", response_model=ImageClassificationResponse)
async def classify_image(
    request: Request,
    service: Annotated[
        ImageClassificationService,
        Depends(get_classification_service),
    ],
) -> ImageClassificationResponse:
    try:
        form = await request.form(
            max_files=1,
            max_fields=5,
            max_part_size=settings.image_upload_max_bytes + 1,
        )
    except (AssertionError, RuntimeError) as exc:
        raise _api_error(503, "SERVICE_UNAVAILABLE", "Multipart upload support is unavailable") from exc

    image = form.get("image")
    if not isinstance(image, UploadFile):
        raise _api_error(422, "INVALID_IMAGE", "image is required")
    model_id = str(form.get("model_id") or "").strip()
    raw_top_k = form.get("top_k")
    try:
        top_k = int(str(raw_top_k)) if raw_top_k not in {None, ""} else settings.classifier_top_k
    except ValueError as exc:
        raise _api_error(422, "VALIDATION_ERROR", "top_k must be an integer") from exc
    if top_k <= 0 or top_k > settings.classifier_max_top_k:
        raise _api_error(
            422,
            "VALIDATION_ERROR",
            f"top_k must be between 1 and {settings.classifier_max_top_k}",
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
        result = service.classify(
            content=content,
            model_id=model_id,
            top_k=top_k,
        )
    except InvalidUploadedImageError as exc:
        raise _api_error(422, "INVALID_IMAGE", str(exc)) from exc
    except UnknownClassifierError as exc:
        raise _api_error(422, "INVALID_MODEL", "The selected classifier is not supported") from exc
    except ClassifierUnavailableError as exc:
        raise _api_error(503, "MODEL_NOT_AVAILABLE", "The selected classifier is not available") from exc
    except ClassifierLoadError as exc:
        raise _api_error(503, "MODEL_LOAD_FAILED", "The selected classifier could not be loaded") from exc
    except ClassificationInferenceError as exc:
        raise _api_error(500, "CLASSIFICATION_FAILED", "Image classification failed") from exc

    return ImageClassificationResponse(
        model=ClassificationModelResponse(
            id=result.model_id,  # type: ignore[arg-type]
            display_name=result.display_name,
            version=result.version,
        ),
        predictions=[
            ClassificationPredictionResponse(**prediction.__dict__)
            for prediction in result.predictions
        ],
        suggested_category_id=result.suggested_category_id,
        timing=ClassificationTimingResponse(**result.timing.__dict__),
    )


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    return HTTPException(status_code=status_code, detail=detail)

