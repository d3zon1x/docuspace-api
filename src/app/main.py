"""FastAPI application factory."""

from fastapi import FastAPI

from app import __version__
from app.api.routers.health import router as health_router


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="DocuSpace API",
        version=__version__,
    )
    app.include_router(health_router)
    return app
