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


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]
