from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository, UserRepositoryProtocol
from app.services.auth import AuthService

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


def get_user_repository(
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRepositoryProtocol:
    return UserRepository(session)


def get_auth_service(
    user_repo: Annotated[UserRepositoryProtocol, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AuthService:
    return AuthService(user_repo, settings)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    user_repo: Annotated[UserRepositoryProtocol, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError(
            "Missing or invalid Authorization header.",
            code="UNAUTHORIZED",
        )

    user_id = decode_access_token(credentials.credentials, settings)
    user = user_repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError(
            "Authenticated user no longer exists.",
            code="UNAUTHORIZED",
        )
    return user
