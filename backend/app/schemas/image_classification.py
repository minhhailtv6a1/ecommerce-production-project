"""Public contracts for classifier capabilities and predictions."""

from typing import Literal

from pydantic import BaseModel, Field


ClassifierId = Literal["alexnet", "resnet50", "vit"]


class ClassifierCapabilityResponse(BaseModel):
    id: ClassifierId
    display_name: str
    available: bool
    version: str | None
    input_size: tuple[int, int] | None


class ClassifierListResponse(BaseModel):
    items: list[ClassifierCapabilityResponse]


class ClassificationModelResponse(BaseModel):
    id: ClassifierId
    display_name: str
    version: str


class ClassificationPredictionResponse(BaseModel):
    rank: int = Field(ge=1)
    category_id: str
    label: str
    logit: float
    probability: float = Field(ge=0, le=1)


class ClassificationTimingResponse(BaseModel):
    preprocess_ms: float = Field(ge=0)
    inference_ms: float = Field(ge=0)
    postprocess_ms: float = Field(ge=0)
    total_ms: float = Field(ge=0)


class ImageClassificationResponse(BaseModel):
    model: ClassificationModelResponse
    predictions: list[ClassificationPredictionResponse]
    suggested_category_id: str
    timing: ClassificationTimingResponse

