"""Unit tests for `/health` and `/ready` endpoints."""

from fastapi.testclient import TestClient

from app.api.routers.health import get_db_checker
from app.main import create_app


def test_health_returns_ok() -> None:
    """GET /health returns 200 OK."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_db_is_reachable() -> None:
    """GET /ready returns 200 when the DB connectivity check passes."""
    app = create_app()
    app.dependency_overrides[get_db_checker] = lambda: lambda: True
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_ready_returns_503_when_db_is_unreachable() -> None:
    """GET /ready returns 503 when the DB connectivity check fails."""
    app = create_app()
    app.dependency_overrides[get_db_checker] = lambda: lambda: False
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
