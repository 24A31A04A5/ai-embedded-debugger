from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import probe_database, reset_database_state


def test_health_endpoint_returns_structured_response(client: TestClient) -> None:
    """Health endpoint returns versioned structured JSON with database probe."""
    with patch("app.routers.health.probe_database", return_value=True):
        response = client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-embedded-debugger-api"
    assert body["version"] == "0.1.0"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["database"]["reachable"] is True


def test_health_endpoint_reports_degraded_when_database_unreachable(
    client: TestClient,
) -> None:
    """Health endpoint reports degraded status when PostgreSQL is unreachable."""
    with patch("app.routers.health.probe_database", return_value=False):
        response = client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"]["status"] == "error"
    assert body["checks"]["database"]["reachable"] is False


@pytest.mark.integration
def test_probe_database_returns_true_when_connection_succeeds() -> None:
    """Database probe succeeds against a configured Neon PostgreSQL instance."""
    import os

    if os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1":
        pytest.skip(
            "Set RUN_DATABASE_INTEGRATION_TESTS=1 and DATABASE_URL in .env to run "
            "live database integration tests"
        )

    reset_database_state()
    assert probe_database() is True


def test_probe_database_returns_false_when_connection_fails() -> None:
    """Database probe returns False quickly when PostgreSQL cannot be reached."""
    invalid_settings = get_settings().model_copy(
        update={
            "database_url": "postgresql+psycopg://invalid:invalid@127.0.0.1:1/nodb",
            "database_connect_timeout": 1,
        },
    )

    with patch("app.core.database.get_settings", return_value=invalid_settings):
        reset_database_state()
        assert probe_database() is False


def test_engine_delegates_connect_to_shared_engine() -> None:
    """Module exposes a lazy engine object that uses the shared engine factory."""
    from unittest.mock import MagicMock

    from app.core.database import engine

    mock_engine = MagicMock()
    with patch("app.core.database.get_engine", return_value=mock_engine) as mock_get:
        engine.connect()
        mock_get.assert_called_once()
        mock_engine.connect.assert_called_once()
