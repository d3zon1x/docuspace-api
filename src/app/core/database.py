import logging
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base class for future SQLAlchemy ORM models."""


@dataclass(slots=True)
class DatabaseManager:
    """Manages SQLAlchemy engine and session factory lifecycle."""

    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def from_settings(cls, settings: Settings) -> "DatabaseManager":
        """Create a new DatabaseManager from application settings."""
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        return cls(engine=engine, session_factory=session_factory)

    def check_connection(self) -> bool:
        """Execute `SELECT 1` against PostgreSQL to verify database reachability."""
        try:
            with self.engine.connect() as connection:
                return connection.execute(text("SELECT 1")).scalar() == 1
        except SQLAlchemyError:
            logger.warning("Database connectivity check failed", exc_info=True)
            return False

    def close(self) -> None:
        self.engine.dispose()
