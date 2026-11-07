from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.config import Settings, get_settings
from app.database import DatabaseManager
from app.repositories.storage import InMemoryStorage, S3Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_manager = DatabaseManager.from_settings(resolved_settings)
        storage = InMemoryStorage() if resolved_settings.storage_backend == "memory" else S3Storage(resolved_settings)
        app.state.settings = resolved_settings
        app.state.db_manager = db_manager
        app.state.db_checker = db_manager.check_connection
        app.state.storage = storage
        try:
            yield
        finally:
            db_manager.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(documents_router)
    return app
