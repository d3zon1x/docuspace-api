"""Integration tests for PostgreSQL connectivity and `/ready` endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.mark.integration
def test_ready_against_real_postgresql() -> None:
    """GET /ready executes `SELECT 1` against a real PostgreSQL instance and returns 200."""
    app = create_app(get_settings())
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


@pytest.mark.integration
def test_ready_returns_503_when_postgresql_unreachable() -> None:
    """GET /ready returns 503 when PostgreSQL is unreachable."""
    bad_settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://app:app@127.0.0.1:59999/app?connect_timeout=1",
    )
    app = create_app(bad_settings)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
