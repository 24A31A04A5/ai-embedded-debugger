from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.database import probe_database

router = APIRouter(tags=["health"])


class DatabaseCheck(BaseModel):
    """Database connectivity probe result."""

    status: Literal["ok", "error"]
    reachable: bool


class HealthResponse(BaseModel):
    """Structured health check response."""

    status: Literal["ok", "degraded"]
    service: str = Field(default="ai-embedded-debugger-api")
    version: str = Field(default="0.1.0")
    checks: dict[str, DatabaseCheck]


class ReadinessResponse(BaseModel):
    """Readiness probe result for deployment orchestrators."""

    status: Literal["ready", "unready"]
    checks: dict[str, DatabaseCheck]


@router.get("/health", response_model=HealthResponse)
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
