from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.core.errors import register_exception_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_manager = DatabaseManager.from_settings(resolved_settings)
        app.state.settings = resolved_settings
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
    app.include_router(auth_router)
    app.include_router(projects_router)
    return app
