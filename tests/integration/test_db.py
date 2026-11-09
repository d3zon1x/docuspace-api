import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.config import Settings, get_settings
from app.database import DatabaseManager
from app.main import create_app
from app.models import Document, Project, ProjectMember, User


@pytest.mark.integration
def test_ready_against_real_postgresql() -> None:
    app = create_app(get_settings())
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


@pytest.mark.integration
def test_ready_returns_503_when_postgresql_unreachable() -> None:
    bad_settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://docuspace:docuspace@127.0.0.1:59999/docuspace?connect_timeout=1",
    )
    app = create_app(bad_settings)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


@pytest.mark.integration
def test_migrations_created_all_core_tables() -> None:
    db_manager = DatabaseManager.from_settings(get_settings())
    try:
        inspector = inspect(db_manager.engine)
        existing_tables = set(inspector.get_table_names())
    finally:
        db_manager.close()

    expected_tables = {
        User.__tablename__,
        Project.__tablename__,
        ProjectMember.__tablename__,
        Document.__tablename__,
    }
    assert expected_tables.issubset(existing_tables)
