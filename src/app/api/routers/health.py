"""Liveness (`/health`) and database readiness (`/ready`) endpoints."""

from collections.abc import Callable
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.schemas.health import HealthResponse, ReadinessResponse

DbChecker = Callable[[], bool]

router = APIRouter(tags=["health"])


def get_db_checker(request: Request) -> DbChecker:
    """Resolve the database connectivity checker from application state."""
    checker = getattr(request.app.state, "db_checker", None)
    if callable(checker):
        return cast(DbChecker, checker)
    return lambda: False


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health() -> HealthResponse:
    """Return 200 when the HTTP server process is up."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_200_OK: {"model": ReadinessResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse},
    },
)
def ready(
    check_db: Annotated[DbChecker, Depends(get_db_checker)],
) -> JSONResponse:
    """Execute `SELECT 1` against PostgreSQL and return 200 if reachable or 503 otherwise."""
    if check_db():
        payload = ReadinessResponse(status="ready", database="ok")
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())

    payload = ReadinessResponse(status="unavailable", database="unavailable")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
