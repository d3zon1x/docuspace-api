from collections.abc import Callable
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DbChecker = Callable[[], bool]

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(default="ok")


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    database: Literal["ok", "unavailable"]


def get_db_checker(request: Request) -> DbChecker:
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
    if check_db():
        payload = ReadinessResponse(status="ready", database="ok")
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())

    payload = ReadinessResponse(status="unavailable", database="unavailable")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
