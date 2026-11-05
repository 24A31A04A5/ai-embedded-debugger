"""Preview-only /health diagnostics: off by default, never leaks hosts or credentials."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.routers.health import database_fingerprint

DEV_URL = "postgresql+psycopg://user:s3cret-pass@ep-dev-123.ap-southeast-1.aws.neon.tech/neondb"


def test_diagnostics_absent_by_default() -> None:
    with patch("app.routers.health.probe_database", return_value=True):
        body = TestClient(app).get("/v1/health").json()
    assert "diagnostics" not in body


def test_diagnostics_when_enabled_hide_host_and_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEALTH_DIAGNOSTICS", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", DEV_URL)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567890")
    get_settings.cache_clear()
    with patch("app.routers.health.probe_database", return_value=True):
        resp = TestClient(app).get("/v1/health")
    text = resp.text
    diag = resp.json()["diagnostics"]
    assert diag["environment"] == "development"
    assert diag["git_sha"] == "abcdef1"
    assert diag["database_fingerprint"] == database_fingerprint(DEV_URL)
    for leaked in ("ep-dev-123", "neon.tech", "s3cret-pass", "user:", "postgresql"):
        assert leaked not in text


def test_fingerprint_distinguishes_hosts() -> None:
    other = DEV_URL.replace("ep-dev-123", "ep-prod-999")
    assert database_fingerprint(DEV_URL) != database_fingerprint(other)
    assert len(database_fingerprint(DEV_URL) or "") == 12
    assert database_fingerprint("not a url") is None
