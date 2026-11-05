import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import reset_database_state
from app.main import app

# Dummy URL for unit tests; probe calls are mocked so no connection is attempted.
UNIT_TEST_DATABASE_URL = "postgresql+psycopg://test:test@127.0.0.1:1/unused"


def integration_tests_enabled() -> bool:
    """Return True when live database integration tests are explicitly enabled."""
    return os.getenv("RUN_DATABASE_INTEGRATION_TESTS") == "1"


@pytest.fixture(autouse=True)
def _configure_test_environment(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Ensure settings and database state are isolated for each test."""
    is_integration = request.node.get_closest_marker("integration") is not None

    if is_integration and integration_tests_enabled():
        get_settings.cache_clear()
        database_url = os.getenv("DATABASE_URL") or get_settings().database_url
        if not database_url:
            pytest.skip("DATABASE_URL must be set in .env for integration tests")
        monkeypatch.setenv("DATABASE_URL", database_url)
    else:
        monkeypatch.setenv("DATABASE_URL", UNIT_TEST_DATABASE_URL)

    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "1")
    # Placeholder so the Clerk client can be constructed in tests. Not a real key: requests
    # without a session token are still rejected with 401 by Clerk's own verification.
    monkeypatch.setenv("CLERK_SECRET_KEY", os.getenv("CLERK_SECRET_KEY") or "sk_test_placeholder")
    monkeypatch.delenv("HEALTH_DIAGNOSTICS", raising=False)
    get_settings.cache_clear()
    reset_database_state()
    yield
    get_settings.cache_clear()
    reset_database_state()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client
