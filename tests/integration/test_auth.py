import uuid
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import BadRequestError, ConflictError, UnauthorizedError
from app.main import create_app
from app.models.user import User
from app.services.auth import AuthService


class FakeUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}
        self._by_login: dict[str, User] = {}

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    def get_by_login(self, login: str) -> User | None:
        return self._by_login.get(login)

    def create(self, *, login: str, password_hash: str) -> User:
        user = User(
            id=uuid.uuid4(),
            login=login,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self._by_id[user.id] = user
        self._by_login[user.login] = user
        return user


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret="test-secret-key-at-least-32-characters-long",
        jwt_expiry_seconds=3600,
    )


def test_auth_service_register_and_login_unit() -> None:
    repo = FakeUserRepository()
    service = AuthService(repo, _settings())

    user = service.register(
        login="alex_dev",
        password="StrongPassword123!",
        repeat_password="StrongPassword123!",
    )
    assert user.login == "alex_dev"

    token, expires_in = service.login(login="alex_dev", password="StrongPassword123!")
    assert isinstance(token, str) and len(token) > 20
    assert expires_in == 3600


def test_auth_service_validation_and_conflicts_unit() -> None:
    repo = FakeUserRepository()
    service = AuthService(repo, _settings())

    with pytest.raises(BadRequestError):
        service.register(
            login="alex_dev",
            password="StrongPassword123!",
            repeat_password="DifferentPassword123!",
        )

    service.register(
        login="alex_dev",
        password="StrongPassword123!",
        repeat_password="StrongPassword123!",
    )

    with pytest.raises(ConflictError):
        service.register(
            login="alex_dev",
            password="StrongPassword123!",
            repeat_password="StrongPassword123!",
        )

    with pytest.raises(UnauthorizedError):
        service.login(login="alex_dev", password="WrongPassword!")

    with pytest.raises(UnauthorizedError):
        service.login(login="unknown_user", password="StrongPassword123!")


@pytest.mark.integration
def test_auth_endpoints_and_get_current_user_integration() -> None:
    app = create_app(get_settings())

    @app.get("/_test/me")
    def _me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
        return {"id": str(current_user.id), "login": current_user.login}

    unique_login = f"user_{uuid.uuid4().hex[:10]}"

    with TestClient(app) as client:
        reg_resp = client.post(
            "/auth",
            json={
                "login": unique_login,
                "password": "StrongPassword123!",
                "repeat_password": "StrongPassword123!",
            },
        )
        assert reg_resp.status_code == 201
        reg_body = reg_resp.json()
        assert reg_body["login"] == unique_login
        assert "id" in reg_body

        dup_resp = client.post(
            "/auth",
            json={
                "login": unique_login,
                "password": "StrongPassword123!",
                "repeat_password": "StrongPassword123!",
            },
        )
        assert dup_resp.status_code == 409
        assert dup_resp.json()["error"]["code"] == "USER_ALREADY_EXISTS"

        mismatch_resp = client.post(
            "/auth",
            json={
                "login": f"other_{uuid.uuid4().hex[:8]}",
                "password": "StrongPassword123!",
                "repeat_password": "MismatchPassword123!",
            },
        )
        assert mismatch_resp.status_code == 400
        assert mismatch_resp.json()["error"]["code"] == "PASSWORDS_DO_NOT_MATCH"

        login_resp = client.post(
            "/login",
            json={"login": unique_login, "password": "StrongPassword123!"},
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 3600
        token = token_data["access_token"]

        unauth_me = client.get("/_test/me")
        assert unauth_me.status_code == 401

        me_resp = client.get(
            "/_test/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json() == {"id": reg_body["id"], "login": unique_login}
