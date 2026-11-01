"""Liveness endpoint."""

from fastapi import APIRouter, status

from app.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health() -> HealthResponse:
    """Return 200 when the process is up."""
    return HealthResponse(status="ok")
