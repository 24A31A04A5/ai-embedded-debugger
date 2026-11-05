import hashlib
import os
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import probe_database

router = APIRouter(tags=["health"])


class DatabaseCheck(BaseModel):
    """Database connectivity probe result."""

    status: Literal["ok", "error"]
    reachable: bool


class EnvironmentDiagnostics(BaseModel):
    """Non-secret facts that let a reviewer confirm which environment answered.

    Only returned when HEALTH_DIAGNOSTICS=true (set on preview/dev services only).
    Never contains hostnames, connection strings or keys: the database is identified
    by a short one-way hash of its host so two environments can be told apart.
    """

    environment: str
    git_sha: str | None = None
    database_fingerprint: str | None = None
    storage_backend: str


class HealthResponse(BaseModel):
    """Structured health check response."""

    status: Literal["ok", "degraded"]
    service: str = Field(default="ai-embedded-debugger-api")
    version: str = Field(default="0.1.0")
    checks: dict[str, DatabaseCheck]
    diagnostics: EnvironmentDiagnostics | None = None


class ReadinessResponse(BaseModel):
    """Readiness probe result for deployment orchestrators."""

    status: Literal["ready", "unready"]
    checks: dict[str, DatabaseCheck]


def database_fingerprint(database_url: str) -> str | None:
    """Return a short SHA-256 of the database host, or None if it cannot be parsed."""
    try:
        host = make_url(database_url).host
    except Exception:
        return None
    if not host:
        return None
    return hashlib.sha256(host.lower().encode("utf-8")).hexdigest()[:12]


def build_diagnostics() -> EnvironmentDiagnostics | None:
    settings = get_settings()
    if not settings.health_diagnostics:
        return None
    sha = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_SHA")
    return EnvironmentDiagnostics(
        environment=settings.app_env,
        git_sha=sha[:7] if sha else None,
        database_fingerprint=database_fingerprint(settings.database_url),
        storage_backend=settings.storage_backend.lower(),
    )


@router.get("/health", response_model=HealthResponse, response_model_exclude_none=True)
def health_check() -> HealthResponse:
    """Return API health status and database connectivity probe."""
    database_reachable = probe_database()
    database_check = DatabaseCheck(
        status="ok" if database_reachable else "error",
        reachable=database_reachable,
    )

    return HealthResponse(
        status="ok" if database_reachable else "degraded",
        checks={"database": database_check},
        diagnostics=build_diagnostics(),
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check(response: Response) -> ReadinessResponse:
    """Readiness probe verifying critical dependency (database) connectivity."""
    database_reachable = probe_database()
    if not database_reachable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if database_reachable else "unready",
        checks={
            "database": DatabaseCheck(
                status="ok" if database_reachable else "error",
                reachable=database_reachable,
            )
        },
    )
