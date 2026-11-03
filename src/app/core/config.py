"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="DocuSpace API")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="postgresql+psycopg://docuspace:docuspace@localhost:5432/docuspace",
    )

    # JWT settings (1 hour = 3600 seconds)
    jwt_secret: str = Field(
        default="dev-secret-key-change-in-production-at-least-32-bytes",
        min_length=16,
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_seconds: int = Field(default=3600, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
