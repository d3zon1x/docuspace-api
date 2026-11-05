from fastapi.testclient import TestClient

from app.api.health import get_db_checker
from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_db_is_reachable() -> None:
    app = create_app()
    app.dependency_overrides[get_db_checker] = lambda: lambda: True
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_ready_returns_503_when_db_is_unreachable() -> None:
    app = create_app()
    app.dependency_overrides[get_db_checker] = lambda: lambda: False
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
