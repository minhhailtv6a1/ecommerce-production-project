"""Application health-check endpoint."""

from fastapi import APIRouter, status

from app.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check backend availability",
)
def health_check() -> HealthResponse:
    """Report that the FastAPI process is available."""
    return HealthResponse(status="ok")
