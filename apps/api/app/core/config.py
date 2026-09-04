import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: apps/api/app/core -> parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", str(REPO_ROOT / ".env")),
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
    cors_origins: list[str] | str = ["http://localhost:3000"]

    # Object Storage Settings

    storage_backend: str = "local"  # "local" or "s3"
    local_storage_path: str = "storage_data"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "ai-embedded-debugger-files"
    s3_region: str = "us-east-1"
    max_upload_size_mb: int = 10

    # RAG / Embedding Settings
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 3072
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Abuse & Resource Limits
    max_files_per_project: int = 50
    max_documents_per_project: int = 20
    max_document_pages: int = 500
    max_chunks_per_document: int = 1000

    # Rate Limiting Settings
    rate_limit_enabled: bool = True
    rate_limit_general_requests_per_minute: int = 120
    rate_limit_ai_requests_per_minute: int = 20
    rate_limit_upload_requests_per_minute: int = 30

    # Product Analytics Settings
    analytics_enabled: bool = True

    # Monitoring & Observability Settings
    request_id_header_name: str = "X-Request-ID"
    expose_error_details: bool = False

    # Database Connection Pool Settings
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_recycle: int = 300

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("postgres://"):
                return "postgresql+psycopg://" + v_stripped[len("postgres://") :]
            if v_stripped.startswith("postgresql://") and not v_stripped.startswith("postgresql+"):
                return "postgresql+psycopg://" + v_stripped[len("postgresql://") :]
            return v_stripped
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return ["http://localhost:3000"]
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in v_stripped.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]
