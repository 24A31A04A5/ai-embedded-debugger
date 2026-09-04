"""Tests for Phase 6.4 — Monitoring & Error Tracking."""

from __future__ import annotations

import logging
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.correlation import is_safe_request_id
from app.core.error_monitoring import LocalErrorTracker, get_error_tracker
from app.core.logging import StructuredLogFormatter, get_request_id, request_id_ctx
from app.main import app

# Add a test router for triggering intentional unhandled exceptions
_test_router = APIRouter(prefix="/test-monitoring", tags=["test-monitoring"])


@_test_router.get("/error-crash")
def trigger_unhandled_crash():
    """Simulate an unexpected internal crash."""
    raise RuntimeError("Unexpected internal crash with db_pass=supersecretpassword and path=/var/internal/db.sqlite")


@_test_router.get("/error-value")
def trigger_value_error():
    raise ValueError("Database connection failed: postgresql://user:secret123@db.prod.internal:5432/main")


@_test_router.get("/validation-test")
def trigger_validation_error(number: int):
    return {"number": number}


app.include_router(_test_router)


# ─────────────────────────────────────────────
# 1. Request Correlation & Request ID Tests
# ─────────────────────────────────────────────


class TestRequestCorrelation:
    def test_request_id_generated_when_missing(self, client: TestClient) -> None:
        """Every response must contain an X-Request-ID header even if none was provided."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        req_id = response.headers["x-request-id"]
        assert len(req_id) >= 16

    def test_request_id_preserved_when_safe(self, client: TestClient) -> None:
        """A safe incoming client request ID must be preserved and reflected in the response."""
        custom_id = "client-req-12345-abcde"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id

    def test_unsafe_request_id_replaced(self, client: TestClient) -> None:
        """Unsafe request IDs (injection characters, newlines, quotes) must be replaced."""
        unsafe_id = "<script>alert(1)</script>\r\nDrop table"
        response = client.get("/health", headers={"X-Request-ID": unsafe_id})
        assert response.status_code == 200
        req_id = response.headers["x-request-id"]
        assert req_id != unsafe_id
        assert "<script>" not in req_id
        # Must be valid UUID format
        assert uuid.UUID(req_id)

    def test_is_safe_request_id_helper(self) -> None:
        assert is_safe_request_id("valid-request-id-1234") is True
        assert is_safe_request_id("abc_123_DEF") is True
        assert is_safe_request_id(str(uuid.uuid4())) is True
        # Too short (<8)
        assert is_safe_request_id("short") is False
        # Too long (>64)
        assert is_safe_request_id("a" * 65) is False
        # Injection or control characters
        assert is_safe_request_id("id\nwith\nnewlines") is False
        assert is_safe_request_id("id with spaces") is False
        assert is_safe_request_id(None) is False


# ─────────────────────────────────────────────
# 2. Global Exception Handling & Safe Responses
# ─────────────────────────────────────────────


class TestGlobalExceptionHandling:
    @pytest.fixture
    def safe_client(self) -> TestClient:
        return TestClient(app, raise_server_exceptions=False)

    def test_unhandled_exception_returns_generic_500(self, safe_client: TestClient) -> None:
        """Unhandled exceptions must return HTTP 500 with a generic message and request ID."""
        response = safe_client.get("/test-monitoring/error-crash")
        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "An unexpected error occurred. Please try again later."
        assert "request_id" in body
        assert response.headers["x-request-id"] == body["request_id"]

    def test_unhandled_exception_never_exposes_secrets_or_paths(self, safe_client: TestClient) -> None:
        """Internal details, passwords, paths, or connection strings must never leak to client."""
        response = safe_client.get("/test-monitoring/error-crash")
        assert response.status_code == 500
        text = response.text
        assert "supersecretpassword" not in text
        assert "/var/internal" not in text
        assert "RuntimeError" not in text

        response2 = safe_client.get("/test-monitoring/error-value")
        assert response2.status_code == 500
        text2 = response2.text
        assert "secret123" not in text2
        assert "db.prod.internal" not in text2
        assert "postgresql://" not in text2

    def test_standard_404_and_422_not_converted_to_500(self, safe_client: TestClient) -> None:
        """HTTPException and validation errors must retain their standard status codes."""
        # 404
        r404 = safe_client.get("/nonexistent-endpoint-xyz")
        assert r404.status_code == 404
        assert "x-request-id" in r404.headers

        # 422 validation error
        r422 = safe_client.get("/test-monitoring/validation-test?number=not_a_number")
        assert r422.status_code == 422
        assert "x-request-id" in r422.headers


# ─────────────────────────────────────────────
# 3. Health & Readiness Probes
# ─────────────────────────────────────────────


class TestHealthAndReadinessProbes:
    def test_health_endpoint_liveness(self, client: TestClient) -> None:
        """Liveness check returns 200 and indicates service status."""
        with patch("app.routers.health.probe_database", return_value=True):
            res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["service"] == "ai-embedded-debugger-api"

    def test_health_v1_compatibility(self, client: TestClient) -> None:
        """Legacy /v1/health continues to function identically."""
        with patch("app.routers.health.probe_database", return_value=True):
            res = client.get("/v1/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_ready_endpoint_success_when_database_reachable(self, client: TestClient) -> None:
        """Readiness check returns 200 and status='ready' when database is reachable."""
        with patch("app.routers.health.probe_database", return_value=True):
            res = client.get("/ready")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"]["status"] == "ok"
        assert body["checks"]["database"]["reachable"] is True

    def test_ready_endpoint_fails_503_when_database_unreachable(self, client: TestClient) -> None:
        """Readiness check returns 503 and status='unready' when database cannot be reached."""
        with patch("app.routers.health.probe_database", return_value=False):
            res = client.get("/ready")
        assert res.status_code == 503
        body = res.json()
        assert body["status"] == "unready"
        assert body["checks"]["database"]["status"] == "error"
        assert body["checks"]["database"]["reachable"] is False

    def test_readiness_probe_does_not_leak_database_credentials(self, client: TestClient) -> None:
        """Even under database failure, no connection strings or credentials appear."""
        with patch("app.routers.health.probe_database", return_value=False):
            res = client.get("/ready")
        assert res.status_code == 503
        text = res.text
        assert "password" not in text
        assert "postgresql" not in text


# ─────────────────────────────────────────────
# 4. Structured Logging & Error Tracking Unit Tests
# ─────────────────────────────────────────────


class TestStructuredLoggingAndErrorTracking:
    def test_structured_formatter_redacts_secrets_in_logs(self) -> None:
        formatter = StructuredLogFormatter()
        token = request_id_ctx.set("test-corr-id-1234")
        try:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Failed with key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q and bearer Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret12345",
                args=(),
                exc_info=None,
            )
            formatted = formatter.format(record)
            assert "AIzaSy" not in formatted
            assert "[REDACTED_GEMINI_KEY]" in formatted
            assert "secret12345" not in formatted
            assert "[REDACTED_TOKEN]" in formatted
            assert "[req:test-corr-id-1234]" in formatted
        finally:
            request_id_ctx.reset(token)

    def test_error_tracker_captures_without_crashing(self) -> None:
        tracker = LocalErrorTracker()
        token = request_id_ctx.set("corr-abc-12345")
        try:
            exc = RuntimeError("Some runtime error with password=testpass123")
            event_id = tracker.capture_exception(
                exc,
                context={"user_id": "u1", "safe_meta": "yes", "api_key": "secret_key"},
            )
            assert event_id == "corr-abc-12345"

            msg_id = tracker.capture_message("Info message", level="info")
            assert msg_id == "corr-abc-12345"
        finally:
            request_id_ctx.reset(token)
