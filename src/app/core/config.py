from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    jwt_secret: str = Field(
        default="dev-secret-key-change-in-production-at-least-32-bytes",
        min_length=16,
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_seconds: int = Field(default=3600, gt=0)

    storage_backend: Literal["s3", "memory"] = Field(default="s3")
    s3_bucket: str = Field(default="docuspace-documents", min_length=1)
    s3_region: str = Field(default="us-east-1", min_length=1)
    s3_endpoint_url: str | None = Field(default="http://localhost:4566")
    aws_access_key_id: str = Field(default="test")
    aws_secret_access_key: str = Field(default="test")

    max_file_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_project_size_bytes: int = Field(default=100 * 1024 * 1024, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
