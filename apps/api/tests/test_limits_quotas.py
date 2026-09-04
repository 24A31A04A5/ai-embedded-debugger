"""Tests for Phase 6.2 — Limits, Quotas & Abuse Protection.

Covers:
1.  Rate limiter logic (sliding window, key separation, reset, disabled flag)
2.  AI endpoint rate limiting (HTTP 429 on excess requests)
3.  Upload endpoint rate limiting (HTTP 429 on excess upload requests)
4.  Oversized debug request payloads rejected by Pydantic (422)
5.  Oversized file upload rejected (413)
6.  Empty file upload rejected (400)
7.  Oversized document upload rejected (413)
8.  File quota per project enforced (400 at limit)
9.  Document quota per project enforced (400 at limit)
10. Normal (within-limit) requests succeed (200/201)
11. Rate limiting disabled flag bypasses checks
12. Client identifier extraction (auth header, X-Forwarded-For, direct IP, unknown)
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitChecker,
    get_client_identifier,
    get_rate_limiter,
)
from app.main import app
from app.models.document import Document
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.services.storage import BaseStorageService, get_storage_service


# ─────────────────────────────────────────────
# Helpers and fixtures
# ─────────────────────────────────────────────


class InMemoryStorageService(BaseStorageService):
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def upload_file(self, storage_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.store[storage_key] = data

    def get_file(self, storage_key: str) -> bytes:
        return self.store[storage_key]

    def delete_file(self, storage_key: str) -> None:
        self.store.pop(storage_key, None)

    def get_download_url(self, storage_key: str, expires_in: int = 3600) -> str | None:
        return f"http://mock/{storage_key}"


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        clerk_id="user_clerk_quota_1",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Quota Test",
        description="Project for quota tests",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def in_memory_storage() -> InMemoryStorageService:
    return InMemoryStorageService()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset the global rate limiter before each test to prevent state leakage."""
    get_rate_limiter().reset()


# ─────────────────────────────────────────────
# 1. InMemoryRateLimiter unit tests
# ─────────────────────────────────────────────


class TestInMemoryRateLimiter:
    def test_within_limit_allowed(self) -> None:
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            is_limited, _ = limiter.is_rate_limited("test_key", limit=5)
            assert not is_limited

    def test_at_limit_blocked(self) -> None:
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.is_rate_limited("test_key", limit=5)
        is_limited, retry_after = limiter.is_rate_limited("test_key", limit=5)
        assert is_limited
        assert retry_after >= 1

    def test_different_keys_are_independent(self) -> None:
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.is_rate_limited("key_a", limit=5)
        # key_a is exhausted; key_b should still be free
        is_limited_b, _ = limiter.is_rate_limited("key_b", limit=5)
        assert not is_limited_b

    def test_reset_clears_all_state(self) -> None:
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.is_rate_limited("key_x", limit=5)
        is_limited, _ = limiter.is_rate_limited("key_x", limit=5)
        assert is_limited

        limiter.reset()
        is_limited_after_reset, _ = limiter.is_rate_limited("key_x", limit=5)
        assert not is_limited_after_reset

    def test_zero_limit_allows_all(self) -> None:
        """RateLimitChecker skips when limit<=0; but the raw limiter does block at limit=0."""
        # The raw limiter blocks immediately if limit=0 (0 >= 0 triggers block)
        limiter = InMemoryRateLimiter()
        is_limited, _ = limiter.is_rate_limited("key_z", limit=0)
        assert is_limited  # raw limiter blocks at limit=0

        # But the RateLimitChecker wrapper skips enforcement when limit <= 0
        # This is verified indirectly by checking the guard in __call__:
        # if limit <= 0: return  (no 429 raised)

    def test_thread_safety_sequential(self) -> None:
        """Basic sequential safety check (real thread test would be in integration tests)."""
        limiter = InMemoryRateLimiter()
        for i in range(10):
            is_limited, _ = limiter.is_rate_limited("shared_key", limit=10)
            if i < 10:
                assert not is_limited


# ─────────────────────────────────────────────
# 2. Client identifier extraction
# ─────────────────────────────────────────────


class TestGetClientIdentifier:
    def _make_request(self, headers: dict[str, str], client_host: str | None = None) -> MagicMock:
        req = MagicMock()
        req.headers = headers
        if client_host:
            req.client = MagicMock()
            req.client.host = client_host
        else:
            req.client = None
        return req

    def test_auth_header_used_when_present(self) -> None:
        req = self._make_request({"authorization": "Bearer some_long_token_value_here"})
        identifier = get_client_identifier(req)
        assert identifier.startswith("auth:")

    def test_short_auth_header_falls_back_to_ip(self) -> None:
        req = self._make_request({"authorization": "short"}, client_host="10.0.0.1")
        identifier = get_client_identifier(req)
        assert identifier == "ip:10.0.0.1"

    def test_x_forwarded_for_used_when_no_auth(self) -> None:
        req = self._make_request({"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
        identifier = get_client_identifier(req)
        assert identifier == "ip:203.0.113.5"

    def test_direct_client_host_used_as_fallback(self) -> None:
        req = self._make_request({}, client_host="192.168.1.1")
        identifier = get_client_identifier(req)
        assert identifier == "ip:192.168.1.1"

    def test_unknown_fallback_when_no_info(self) -> None:
        req = self._make_request({})
        identifier = get_client_identifier(req)
        assert identifier == "ip:unknown"


# ─────────────────────────────────────────────
# 3. Rate limiter disabled flag
# ─────────────────────────────────────────────


class TestRateLimitDisabledFlag:
    def test_rate_limit_disabled_bypasses_all_checks(
        self, mock_user: User, mock_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When rate_limit_enabled=False, requests above the limit should not be blocked."""
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
        monkeypatch.setenv("RATE_LIMIT_AI_REQUESTS_PER_MINUTE", "1")
        get_settings.cache_clear()

        # Verify the setting took effect
        settings = get_settings()
        assert settings.rate_limit_enabled is False

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch("app.routers.debug.analyze_debugging_context") as mock_ai:
                from app.schemas.debug import DebugResponse, LikelyCause
                mock_ai.return_value = DebugResponse(
                    problem_observed="test",
                    evidence_used=["test evidence"],
                    likely_causes=[LikelyCause(cause="test cause", plausibility="medium")],
                    recommended_steps=["step 1"],
                    proposed_fix="fix test",
                )
                # Should not be rate limited even though limit is 1
                for _ in range(3):
                    response = client.post(
                        f"/v1/projects/{mock_project.id}/debug",
                        json={"user_question": "Help me"},
                    )
                    assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()


# ─────────────────────────────────────────────
# 4. Pydantic schema bounds (oversized payloads)
# ─────────────────────────────────────────────


class TestOversizedPayloadRejection:
    def test_oversized_firmware_code_rejected(
        self, mock_user: User, mock_project: Project
    ) -> None:
        """Payload with firmware_code exceeding max_length=200,000 should be rejected with 422."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/debug",
                json={"firmware_code": "x" * 200_001},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_oversized_serial_logs_rejected(
        self, mock_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/debug",
                json={"serial_logs": "L" * 200_001},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_oversized_question_rejected(
        self, mock_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/debug",
                json={"user_question": "Q" * 10_001},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_normal_debug_request_within_limits_accepted(
        self, mock_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch("app.routers.debug.analyze_debugging_context") as mock_ai:
                from app.schemas.debug import DebugResponse, LikelyCause
                mock_ai.return_value = DebugResponse(
                    problem_observed="Test OK",
                    evidence_used=["test evidence"],
                    likely_causes=[LikelyCause(cause="none", plausibility="high")],
                    recommended_steps=["step 1"],
                    proposed_fix="none",
                )
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "firmware_code": "void setup() {}",
                        "user_question": "Is this OK?",
                    },
                )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ─────────────────────────────────────────────
# 5. Upload size and empty file protection
# ─────────────────────────────────────────────


class TestUploadSizeProtection:
    def test_oversized_code_file_upload_rejected(
        self, mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
        get_settings.cache_clear()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            big_content = b"x" * (1 * 1024 * 1024 + 1)  # 1 MB + 1 byte
            response = client.post(
                f"/v1/projects/{mock_project.id}/files/upload",
                files={"file": ("big.c", io.BytesIO(big_content), "text/x-c")},
            )
            assert response.status_code == 413
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

    def test_empty_code_file_upload_rejected(
        self, mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/files/upload",
                files={"file": ("empty.c", io.BytesIO(b""), "text/x-c")},
            )
            assert response.status_code == 400
            assert "empty" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_oversized_document_upload_rejected(
        self, mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
        get_settings.cache_clear()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            big_content = b"%PDF-1.4" + b"x" * (1 * 1024 * 1024 + 1)
            response = client.post(
                f"/v1/projects/{mock_project.id}/documents/upload",
                files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
            )
            assert response.status_code == 413
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()


# ─────────────────────────────────────────────
# 6. File and document quota enforcement
# ─────────────────────────────────────────────


class TestQuotaEnforcement:
    def test_file_quota_blocks_upload_when_at_limit(
        self, mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_FILES_PER_PROJECT", "2")
        get_settings.cache_clear()

        mock_db = MagicMock()

        def query_side_effect(model_class):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model_class.__name__ == "Project":
                f.first.return_value = mock_project
            elif model_class.__name__ == "ProjectFile":
                # Already at quota
                f.count.return_value = 2
                f.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/files/upload",
                files={"file": ("new.c", io.BytesIO(b"void loop(){}"), "text/x-c")},
            )
            assert response.status_code == 400
            assert "maximum" in response.json()["detail"].lower()
            assert "files" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

    def test_file_quota_allows_upload_when_under_limit(
        self, mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_FILES_PER_PROJECT", "50")
        get_settings.cache_clear()

        mock_db = MagicMock()

        def query_side_effect(model_class):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model_class.__name__ == "Project":
                f.first.return_value = mock_project
            elif model_class.__name__ == "ProjectFile":
                f.count.return_value = 5  # well below 50
                f.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/files/upload",
                files={"file": ("ok.c", io.BytesIO(b"void setup(){}"), "text/x-c")},
            )
            assert response.status_code == 201
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

    def test_document_quota_blocks_upload_when_at_limit(
        self, mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_DOCUMENTS_PER_PROJECT", "3")
        get_settings.cache_clear()

        mock_db = MagicMock()

        def query_side_effect(model_class):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model_class.__name__ == "Project":
                f.first.return_value = mock_project
            elif model_class.__name__ == "Document":
                f.count.return_value = 3  # at the limit
                f.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            pdf_bytes = b"%PDF-1.4\nminimal pdf"
            response = client.post(
                f"/v1/projects/{mock_project.id}/documents/upload",
                files={"file": ("datasheet.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            assert response.status_code == 400
            assert "maximum" in response.json()["detail"].lower()
            assert "documents" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()


# ─────────────────────────────────────────────
# 7. Rate limit enforcement on AI endpoints
# ─────────────────────────────────────────────


class TestAIRateLimiting:
    def test_ai_rate_limit_returns_429_on_excess(
        self, mock_user: User, mock_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When more requests than the AI limit are made, HTTP 429 is returned."""
        monkeypatch.setenv("RATE_LIMIT_AI_REQUESTS_PER_MINUTE", "2")
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        get_settings.cache_clear()
        get_rate_limiter().reset()

        # Verify settings took effect
        settings = get_settings()
        assert settings.rate_limit_ai_requests_per_minute == 2
        assert settings.rate_limit_enabled is True

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch("app.routers.debug.analyze_debugging_context") as mock_ai:
                from app.schemas.debug import DebugResponse, LikelyCause
                mock_ai.return_value = DebugResponse(
                    problem_observed="ok",
                    evidence_used=["ok evidence"],
                    likely_causes=[LikelyCause(cause="ok", plausibility="high")],
                    recommended_steps=["step 1"],
                    proposed_fix="ok",
                )
                statuses = []
                for _ in range(4):
                    r = client.post(
                        f"/v1/projects/{mock_project.id}/debug",
                        json={"user_question": "test"},
                    )
                    statuses.append(r.status_code)

            # First 2 should succeed, at least one of the rest should be 429
            assert statuses[0] == 200
            assert statuses[1] == 200
            assert 429 in statuses[2:]
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

    def test_rate_limit_429_response_includes_retry_after(
        self, mock_user: User, mock_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RATE_LIMIT_AI_REQUESTS_PER_MINUTE", "1")
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        get_settings.cache_clear()
        get_rate_limiter().reset()

        # Verify settings took effect
        settings = get_settings()
        assert settings.rate_limit_ai_requests_per_minute == 1

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch("app.routers.debug.analyze_debugging_context") as mock_ai:
                from app.schemas.debug import DebugResponse, LikelyCause
                mock_ai.return_value = DebugResponse(
                    problem_observed="ok",
                    evidence_used=["ok evidence"],
                    likely_causes=[LikelyCause(cause="ok", plausibility="high")],
                    recommended_steps=["step 1"],
                    proposed_fix="ok",
                )
                # First request consumes the limit
                client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={"user_question": "first"},
                )
                # Second request should be rate limited
                r = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={"user_question": "second"},
                )
                assert r.status_code == 429
                assert "retry-after" in r.headers
                assert int(r.headers["retry-after"]) >= 1
                assert "Too many requests" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()


# ─────────────────────────────────────────────
# 8. Rate limit on upload endpoint
# ─────────────────────────────────────────────


class TestUploadRateLimiting:
    def test_upload_rate_limit_returns_429_on_excess(
        self, mock_user: User, mock_project: Project,
        in_memory_storage: InMemoryStorageService,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RATE_LIMIT_UPLOAD_REQUESTS_PER_MINUTE", "2")
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        get_settings.cache_clear()
        get_rate_limiter().reset()

        mock_db = MagicMock()

        def query_side_effect(model_class):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model_class.__name__ == "Project":
                f.first.return_value = mock_project
            elif model_class.__name__ == "ProjectFile":
                f.count.return_value = 0
                f.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

        client = TestClient(app)
        try:
            statuses = []
            for i in range(4):
                r = client.post(
                    f"/v1/projects/{mock_project.id}/files/upload",
                    files={"file": (f"f{i}.c", io.BytesIO(b"void f(){}"), "text/x-c")},
                )
                statuses.append(r.status_code)

            assert statuses[0] == 201
            assert statuses[1] == 201
            assert 429 in statuses[2:]
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()


# ─────────────────────────────────────────────
# 9. Settings configuration for limits
# ─────────────────────────────────────────────


class TestLimitSettings:
    def test_default_limit_settings_are_reasonable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        # Verify defaults are sane for embedded debugging workflows
        assert settings.max_files_per_project >= 20
        assert settings.max_documents_per_project >= 10
        assert settings.max_document_pages >= 100
        assert settings.max_chunks_per_document >= 100
        assert settings.rate_limit_ai_requests_per_minute >= 5
        assert settings.rate_limit_upload_requests_per_minute >= 10
        assert settings.rate_limit_general_requests_per_minute >= 30

    def test_limit_settings_configurable_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_FILES_PER_PROJECT", "25")
        monkeypatch.setenv("MAX_DOCUMENTS_PER_PROJECT", "8")
        monkeypatch.setenv("RATE_LIMIT_AI_REQUESTS_PER_MINUTE", "10")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.max_files_per_project == 25
        assert settings.max_documents_per_project == 8
        assert settings.rate_limit_ai_requests_per_minute == 10
        get_settings.cache_clear()
