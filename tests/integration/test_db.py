"""Integration tests for PostgreSQL connectivity, schema migrations, and `/ready`."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.main import create_app
from app.models import Document, DocumentVersion, Project, ProjectMember, User


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
        database_url="postgresql+psycopg://docuspace:docuspace@127.0.0.1:59999/docuspace?connect_timeout=1",
    )
    app = create_app(bad_settings)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


@pytest.mark.integration
def test_migrations_created_all_core_tables() -> None:
    """Verify that Alembic migrations created all 5 ORM tables in PostgreSQL."""
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
        DocumentVersion.__tablename__,
    }
    assert expected_tables.issubset(existing_tables)
