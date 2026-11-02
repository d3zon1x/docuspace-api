"""Health and readiness response schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness response."""

    status: Literal["ok"] = Field(default="ok")


class ReadinessResponse(BaseModel):
    """Database readiness response."""

    status: Literal["ready", "unavailable"]
    database: Literal["ok", "unavailable"]
