import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def _register_and_login(client: TestClient, login: str) -> str:
    reg = client.post(
        "/auth",
        json={
            "login": login,
            "password": "StrongPassword123!",
            "repeat_password": "StrongPassword123!",
        },
    )
    assert reg.status_code == 201

    auth = client.post("/login", json={"login": login, "password": "StrongPassword123!"})
    assert auth.status_code == 200
    return str(auth.json()["access_token"])


@pytest.mark.integration
def test_projects_crud_roles_and_invite_flow() -> None:
    app = create_app(get_settings())
    owner_login = f"owner_{uuid.uuid4().hex[:8]}"
    participant_login = f"part_{uuid.uuid4().hex[:8]}"
    outsider_login = f"out_{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        owner_token = _register_and_login(client, owner_login)
        part_token = _register_and_login(client, participant_login)
        outsider_token = _register_and_login(client, outsider_login)

        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        part_headers = {"Authorization": f"Bearer {part_token}"}
        outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

        create_resp = client.post(
            "/projects",
            headers=owner_headers,
            json={"name": "Alpha Project", "description": "Initial description"},
        )
        assert create_resp.status_code == 201
        project_data = create_resp.json()
        project_id = project_data["id"]
        assert project_data["name"] == "Alpha Project"
        assert project_data["role"] == "owner"
        assert project_data["total_size_bytes"] == 0

        list_resp = client.get("/projects", headers=owner_headers)
        assert list_resp.status_code == 200
        assert any(p["id"] == project_id for p in list_resp.json())

        outsider_info = client.get(f"/project/{project_id}/info", headers=outsider_headers)
        assert outsider_info.status_code == 404
        assert outsider_info.json()["error"]["code"] == "PROJECT_NOT_FOUND"

        invite_resp = client.post(
            f"/project/{project_id}/invite",
            params={"user": participant_login},
            headers=owner_headers,
        )
        assert invite_resp.status_code == 200
        assert invite_resp.json() == {
            "project_id": project_id,
            "invited_user": participant_login,
            "role": "participant",
        }

        dup_invite = client.post(
            f"/project/{project_id}/invite",
            params={"user": participant_login},
            headers=owner_headers,
        )
        assert dup_invite.status_code == 409
        assert dup_invite.json()["error"]["code"] == "ALREADY_PROJECT_MEMBER"

        unknown_invite = client.post(
            f"/project/{project_id}/invite",
            params={"user": "nonexistent_user_12345"},
            headers=owner_headers,
        )
        assert unknown_invite.status_code == 404
        assert unknown_invite.json()["error"]["code"] == "USER_NOT_FOUND"

        part_info = client.get(f"/project/{project_id}/info", headers=part_headers)
        assert part_info.status_code == 200
        assert part_info.json()["role"] == "participant"

        update_resp = client.put(
            f"/project/{project_id}/info",
            headers=part_headers,
            json={"name": "Alpha Project v2", "description": "Updated by participant"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Alpha Project v2"
        assert update_resp.json()["description"] == "Updated by participant"

        part_invite = client.post(
            f"/project/{project_id}/invite",
            params={"user": outsider_login},
            headers=part_headers,
        )
        assert part_invite.status_code == 403
        assert part_invite.json()["error"]["code"] == "OWNER_REQUIRED"

        part_delete = client.delete(f"/project/{project_id}", headers=part_headers)
        assert part_delete.status_code == 403
        assert part_delete.json()["error"]["code"] == "OWNER_REQUIRED"

        owner_delete = client.delete(f"/project/{project_id}", headers=owner_headers)
        assert owner_delete.status_code == 200
        assert owner_delete.json() == {"id": project_id, "status": "deleted"}

        after_delete = client.get(f"/project/{project_id}/info", headers=owner_headers)
        assert after_delete.status_code == 404
