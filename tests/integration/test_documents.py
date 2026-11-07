import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
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


def _memory_storage_settings() -> Settings:
    base = get_settings()
    return Settings(
        _env_file=None,
        database_url=base.database_url,
        jwt_secret=base.jwt_secret,
        storage_backend="memory",
        max_file_size_bytes=1024,
        max_project_size_bytes=2048,
    )


@pytest.mark.integration
def test_documents_lifecycle_upload_download_update_delete() -> None:
    app = create_app(_memory_storage_settings())
    owner_login = f"doc_owner_{uuid.uuid4().hex[:8]}"
    outsider_login = f"doc_out_{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        owner_token = _register_and_login(client, owner_login)
        outsider_token = _register_and_login(client, outsider_login)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

        proj_resp = client.post(
            "/projects",
            headers=owner_headers,
            json={"name": "Docs Project", "description": "Testing documents"},
        )
        project_id = proj_resp.json()["id"]

        upload_resp = client.post(
            f"/project/{project_id}/documents",
            headers=owner_headers,
            files=[("files", ("spec.pdf", b"%PDF-1.4 sample content", "application/pdf"))],
        )
        assert upload_resp.status_code == 201
        uploaded_docs = upload_resp.json()
        assert len(uploaded_docs) == 1
        doc_id = uploaded_docs[0]["id"]
        assert isinstance(doc_id, int)
        assert uploaded_docs[0]["filename"] == "spec.pdf"

        list_resp = client.get(f"/project/{project_id}/documents", headers=owner_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        dup_resp = client.post(
            f"/project/{project_id}/documents",
            headers=owner_headers,
            files=[("files", ("spec.pdf", b"%PDF-1.4 another", "application/pdf"))],
        )
        assert dup_resp.status_code == 409

        bad_ext_resp = client.post(
            f"/project/{project_id}/documents",
            headers=owner_headers,
            files=[("files", ("malware.exe", b"binary", "application/octet-stream"))],
        )
        assert bad_ext_resp.status_code == 415

        too_large_resp = client.post(
            f"/project/{project_id}/documents",
            headers=owner_headers,
            files=[("files", ("huge.pdf", b"x" * 1500, "application/pdf"))],
        )
        assert too_large_resp.status_code == 413

        outsider_dl = client.get(f"/document/{doc_id}", headers=outsider_headers)
        assert outsider_dl.status_code == 403

        dl_resp = client.get(f"/document/{doc_id}", headers=owner_headers)
        assert dl_resp.status_code == 200
        assert dl_resp.content == b"%PDF-1.4 sample content"
        assert "spec.pdf" in dl_resp.headers["content-disposition"]

        update_resp = client.put(
            f"/document/{doc_id}",
            headers=owner_headers,
            files={"file": ("updated_spec.docx", b"PK\x03\x04 docx content bytes", "application/octet-stream")},
        )
        assert update_resp.status_code == 200
        updated_body = update_resp.json()
        assert updated_body["filename"] == "updated_spec.docx"

        del_resp = client.delete(f"/document/{doc_id}", headers=owner_headers)
        assert del_resp.status_code == 200
        assert del_resp.json() == {"id": doc_id, "status": "deleted"}

        after_del = client.get(f"/document/{doc_id}", headers=owner_headers)
        assert after_del.status_code == 404
