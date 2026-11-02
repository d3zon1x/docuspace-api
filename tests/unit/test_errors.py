"""Unit tests for standardized application error handling."""

from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    UnauthorizedError,
)
from app.main import create_app


class _SamplePayload(BaseModel):
    name: str


def test_app_errors_return_unified_error_envelope() -> None:
    app = create_app()

    @app.get("/_test/not-found")
    def _raise_not_found() -> None:
        raise NotFoundError("Project not found.", code="PROJECT_NOT_FOUND")

    @app.get("/_test/other-errors/{kind}")
    def _raise_other(kind: str) -> None:
        mapping = {
            "bad": BadRequestError("Invalid input."),
            "unauth": UnauthorizedError("Missing token."),
            "forbidden": ForbiddenError("Owner required."),
            "conflict": ConflictError("Duplicate filename."),
            "large": PayloadTooLargeError("Quota exceeded."),
        }
        raise mapping[kind]

    client = TestClient(app)

    res = client.get("/_test/not-found")
    assert res.status_code == 404
    assert res.json() == {
        "error": {
            "code": "PROJECT_NOT_FOUND",
            "message": "Project not found.",
        }
    }

    expected = [
        ("bad", 400, "BAD_REQUEST"),
        ("unauth", 401, "UNAUTHORIZED"),
        ("forbidden", 403, "FORBIDDEN"),
        ("conflict", 409, "CONFLICT"),
        ("large", 413, "PAYLOAD_TOO_LARGE"),
    ]
    for kind, status_code, code in expected:
        resp = client.get(f"/_test/other-errors/{kind}")
        assert resp.status_code == status_code
        assert resp.json()["error"]["code"] == code


def test_validation_error_returns_unified_error_envelope() -> None:
    """FastAPI 422 RequestValidationError is formatted using the unified error envelope."""
    app = create_app()

    @app.post("/_test/validate")
    def _validate(body: _SamplePayload) -> dict[str, str]:
        return {"name": body.name}

    client = TestClient(app)
    res = client.post("/_test/validate", json={})

    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["error"]["message"], str)
