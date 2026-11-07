import uuid
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.config import get_settings
from app.main import create_app
from app.models import User


@pytest.mark.integration
def test_auth_endpoints_and_get_current_user_integration() -> None:
    app = create_app(get_settings())

    @app.get("/_test/me")
    def _me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, int | str]:
        return {"id": current_user.id, "login": current_user.login}

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
        assert isinstance(reg_body["id"], int)

        dup_resp = client.post(
            "/auth",
            json={
                "login": unique_login,
                "password": "StrongPassword123!",
                "repeat_password": "StrongPassword123!",
            },
        )
        assert dup_resp.status_code == 409

        mismatch_resp = client.post(
            "/auth",
            json={
                "login": f"other_{uuid.uuid4().hex[:8]}",
                "password": "StrongPassword123!",
                "repeat_password": "MismatchPassword123!",
            },
        )
        assert mismatch_resp.status_code == 400

        bad_login = client.post(
            "/login",
            json={"login": unique_login, "password": "WrongPassword!"},
        )
        assert bad_login.status_code == 401

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
