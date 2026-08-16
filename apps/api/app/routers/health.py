from typing import Literal

from fastapi import APIRouter
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
