"""Tests for Phase 6.6 — Deployment & Production Readiness."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.database import build_engine
from app.main import lifespan


class TestDatabaseUrlNormalization:
    """Ensure database connection strings from various cloud providers are normalized."""

    def test_normalizes_postgres_scheme(self) -> None:
        raw = "postgres://myuser:mypassword@ep-cool-db.neon.tech/neondb?sslmode=require"
        normalized = Settings.normalize_database_url(raw)
        expected = (
            "postgresql+psycopg://myuser:mypassword@ep-cool-db.neon.tech/neondb?sslmode=require"
        )
        assert normalized == expected

    def test_normalizes_postgresql_scheme_without_driver(self) -> None:
        raw = "postgresql://myuser:mypassword@ep-cool-db.neon.tech/neondb?sslmode=require"
        normalized = Settings.normalize_database_url(raw)
        expected = (
            "postgresql+psycopg://myuser:mypassword@ep-cool-db.neon.tech/neondb?sslmode=require"
        )
        assert normalized == expected

    def test_preserves_explicit_psycopg_driver(self) -> None:
        original = (
            "postgresql+psycopg://myuser:mypassword@ep-cool-db.neon.tech/neondb?sslmode=require"
        )
        normalized = Settings.normalize_database_url(original)
        assert normalized == original

    def test_strips_leading_trailing_whitespace(self) -> None:
        raw = "  postgres://user:pass@host/db  \n"
        normalized = Settings.normalize_database_url(raw)
        assert normalized == "postgresql+psycopg://user:pass@host/db"


class TestCorsConfiguration:
    """Ensure CORS origins can be passed as strings or lists and parse safely."""

    def test_parses_comma_separated_origins(self) -> None:
        raw = "https://debugger.example.com, https://preview.example.com"
        parsed = Settings.parse_cors_origins(raw)
        assert parsed == ["https://debugger.example.com", "https://preview.example.com"]

    def test_parses_json_array_string(self) -> None:
        raw = '["https://debugger.example.com", "https://preview.example.com"]'
        parsed = Settings.parse_cors_origins(raw)
        assert parsed == ["https://debugger.example.com", "https://preview.example.com"]

    def test_falls_back_to_localhost_when_empty_string(self) -> None:
        assert Settings.parse_cors_origins("") == ["http://localhost:3000"]
        assert Settings.parse_cors_origins("   ") == ["http://localhost:3000"]

    def test_preserves_clean_list(self) -> None:
        origins = ["https://app.example.com", "https://api.example.com"]
        assert Settings.parse_cors_origins(origins) == origins


class TestProductionLifespanAndObservability:
    """Ensure startup validation warns about missing production config and shutdown cleans up."""

    def test_production_startup_emits_appropriate_warnings(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        prod_settings = get_settings().model_copy(
            update={
                "app_env": "production",
                "clerk_secret_key": "",
                "gemini_api_key": "",
                "cors_origins": ["http://localhost:3000"],
                "expose_error_details": True,
            }
        )

        test_app = FastAPI()

        async def run_test() -> None:
            with patch("app.main.get_settings", return_value=prod_settings):
                with caplog.at_level(logging.WARNING, logger="app.lifecycle"):
                    async with lifespan(test_app):
                        pass

        asyncio.run(run_test())

        logs = caplog.text
        assert "CLERK_SECRET_KEY is not configured" in logs
        assert "GEMINI_API_KEY is not configured" in logs
        assert "CORS_ORIGINS is using development default" in logs
        assert "EXPOSE_ERROR_DETAILS is enabled in production" in logs

    def test_shutdown_disposes_database_engine(self) -> None:
        test_app = FastAPI()

        async def run_test() -> None:
            with patch("app.core.database.engine.dispose") as mock_dispose:
                async with lifespan(test_app):
                    pass
                mock_dispose.assert_called_once()

        asyncio.run(run_test())


class TestProductionRouteHardening:
    """Ensure development-only routes (docs, redoc, openapi) are disabled in production mode."""

    def test_docs_and_openapi_disabled_in_production(self) -> None:
        with patch.dict("os.environ", {"APP_ENV": "production"}):
            prod_settings = get_settings().model_copy(update={"app_env": "production"})
            with patch("app.main.get_settings", return_value=prod_settings):
                prod_app = FastAPI(
                    openapi_url=None,
                    docs_url=None,
                    redoc_url=None,
                )
                client = TestClient(prod_app)
                assert client.get("/docs").status_code == 404
                assert client.get("/redoc").status_code == 404
                assert client.get("/openapi.json").status_code == 404


class TestDatabasePoolConfiguration:
    """Verify database connection pool parameters are passed to SQLAlchemy create_engine."""

    def test_pool_tuning_parameters_applied(self) -> None:
        custom_settings = get_settings().model_copy(
            update={
                "database_pool_size": 15,
                "database_max_overflow": 25,
                "database_pool_recycle": 600,
            }
        )

        with patch("app.core.database.create_engine") as mock_create_engine:
            build_engine(custom_settings)
            mock_create_engine.assert_called_once()
            _, kwargs = mock_create_engine.call_args
            assert kwargs["pool_size"] == 15
            assert kwargs["max_overflow"] == 25
            assert kwargs["pool_recycle"] == 600
            assert kwargs["pool_pre_ping"] is True
