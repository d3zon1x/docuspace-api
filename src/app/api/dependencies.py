from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import DatabaseManager
from app.errors import InvalidTokenError
from app.models import User
from app.repositories.document import DocumentRepository
from app.repositories.project import ProjectRepository
from app.repositories.storage import InMemoryStorage, S3Storage, StorageBackend
from app.repositories.user import UserRepository
from app.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()


def get_db_session(request: Request) -> Iterator[Session]:
    db_manager = getattr(request.app.state, "db_manager", None)
    if not isinstance(db_manager, DatabaseManager):
        raise RuntimeError("DatabaseManager is not initialized on app.state")

    session = db_manager.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_storage(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> StorageBackend:
    storage = getattr(request.app.state, "storage", None)
    if storage is not None:
        return cast(StorageBackend, storage)
    if settings.storage_backend == "memory":
        return InMemoryStorage()
    return S3Storage(settings)


def get_user_repository(session: Annotated[Session, Depends(get_db_session)]) -> UserRepository:
    return UserRepository(session)


def get_project_repository(
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> ProjectRepository:
    return ProjectRepository(session, storage)


def get_document_repository(
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> DocumentRepository:
    return DocumentRepository(session, storage, settings)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from e

    user = user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists",
        )
    return user
