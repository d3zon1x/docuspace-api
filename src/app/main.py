"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routers.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.core.errors import register_exception_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_manager = DatabaseManager.from_settings(resolved_settings)
        app.state.db_manager = db_manager
        app.state.db_checker = db_manager.check_connection
        try:
            yield
        finally:
            db_manager.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    return app
