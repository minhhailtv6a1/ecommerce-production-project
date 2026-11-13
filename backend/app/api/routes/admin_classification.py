"""Admin-only classifier capability and category-suggestion routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_classification_service, get_classifier_registry
from app.api.routes.auth import require_admin
from app.api.routes.image_classification import classify_image, list_classifiers
from app.classifiers.registry import ClassifierRegistry
from app.repositories.users import UserRecord
from app.schemas.image_classification import ClassifierListResponse, ImageClassificationResponse
from app.services.image_classification import ImageClassificationService


router = APIRouter(prefix="/admin", tags=["admin-classification"])


@router.get("/classifiers", response_model=ClassifierListResponse)
def list_admin_classifiers(
    _admin: Annotated[UserRecord, Depends(require_admin)],
    registry: Annotated[ClassifierRegistry, Depends(get_classifier_registry)],
) -> ClassifierListResponse:
    return list_classifiers(registry)


@router.post("/classification/predict", response_model=ImageClassificationResponse)
async def predict_admin_category(
    request: Request,
    _admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[ImageClassificationService, Depends(get_classification_service)],
) -> ImageClassificationResponse:
    return await classify_image(request, service)
