from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: apps/api/app/core -> parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    database_connect_timeout: int = 5
    app_env: str = "development"
    log_level: str = "INFO"
    clerk_secret_key: str = ""
    gemini_api_key: str = ""

    # Object Storage Settings
    storage_backend: str = "local"  # "local" or "s3"
    local_storage_path: str = "storage_data"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "ai-embedded-debugger-files"
    s3_region: str = "us-east-1"
    max_upload_size_mb: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]
