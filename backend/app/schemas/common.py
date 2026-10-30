"""Schemas shared by API routes."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response returned when the backend process is operational."""

    status: Literal["ok"] = Field(examples=["ok"])


class ApiErrorResponse(BaseModel):
    """Stable error shape shared by the frontend-facing API."""

    code: str = Field(examples=["VALIDATION_ERROR"])
    message: str = Field(examples=["Invalid request parameters"])
    field_errors: dict[str, Any] = Field(
        examples=[{"email": "Invalid email address"}]
    )
    request_id: str = Field(examples=["86282240-0a67-4c5d-90f6-8558ea9df6a1"])
