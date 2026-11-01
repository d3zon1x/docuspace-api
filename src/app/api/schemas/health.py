"""Health check response schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness response."""

    status: Literal["ok"] = Field(default="ok")
