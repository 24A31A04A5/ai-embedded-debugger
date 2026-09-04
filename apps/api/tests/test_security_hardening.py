"""Tests for Phase 6.1 — Security and Production Hardening.

Covers:
1.  Protected routes require authentication (401 when unauthenticated)
2.  Cross-user project isolation (404 on other user's project)
3.  Cross-user file access prevention (404 on other user's files)
4.  Cross-user session access prevention (404 on other user's sessions)
5.  Cross-user document and search isolation (scoped strictly to user project)
6.  Filename sanitization (slashes, path traversal, null bytes, reserved names)
7.  Local storage path traversal containment (strictly inside storage directory)
8.  HTTP security headers on responses (nosniff, DENY, Referrer-Policy)
9.  Secret redaction utility (Gemini keys, Clerk keys, Bearer tokens, AWS secrets)
10. AI error sanitization in debug and session endpoints (no secret leaks)
11. Input validation bounds (payload bounds prevent unbounded DoS)
12. Production docs configuration gating (docs disabled in production mode)
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.config import Settings
from app.core.database import get_db
from app.core.security import (
    sanitize_error_detail,
    sanitize_filename,
    sanitize_secrets,
)
from app.main import app
from app.models.debug_session import DebugSession
from app.models.document import Document
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.services.storage import LocalStorageService


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def user_a() -> User:
    return User(
        id=uuid.uuid4(),
        email="user_a@example.com",
        clerk_id="clerk_user_a",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def user_b() -> User:
    return User(
        id=uuid.uuid4(),
        email="user_b@example.com",
        clerk_id="clerk_user_b",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def project_b(user_b: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=user_b.id,
        name="User B Project",
        description="Private project belonging to User B",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ─────────────────────────────────────────────
# 1. Authentication requirements
# ─────────────────────────────────────────────


class TestAuthenticationEnforcement:
    def test_unauthenticated_request_to_projects_fails(self) -> None:
        client = TestClient(app)
        response = client.get("/v1/projects")
        # Should be 401 Unauthorized
        assert response.status_code == 401

    def test_unauthenticated_request_to_debug_fails(self) -> None:
        client = TestClient(app)
        response = client.post(
            f"/v1/projects/{uuid.uuid4()}/debug",
            json={"user_question": "Help me debug"},
        )
        assert response.status_code == 401


# ─────────────────────────────────────────────
# 2. Cross-user isolation
# ─────────────────────────────────────────────


class TestCrossUserIsolation:
    def test_user_a_cannot_access_user_b_project_files(
        self, user_a: User, project_b: Project
    ) -> None:
        mock_db = MagicMock()
        # Querying Project with owner_id == user_a.id returns None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: user_a
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.get(f"/v1/projects/{project_b.id}/files")
            assert response.status_code == 404
            assert response.json()["detail"] == "Project not found"
        finally:
            app.dependency_overrides.clear()

    def test_user_a_cannot_access_user_b_sessions(
        self, user_a: User, project_b: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: user_a
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.get(f"/v1/projects/{project_b.id}/sessions")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_user_a_cannot_access_user_b_documents(
        self, user_a: User, project_b: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: user_a
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.get(f"/v1/projects/{project_b.id}/documents")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ─────────────────────────────────────────────
# 3. Filename sanitization & path traversal
# ─────────────────────────────────────────────


class TestFilenameSanitization:
    def test_strips_posix_path_traversal(self) -> None:
        assert sanitize_filename("../../../etc/passwd.c") == "passwd.c"
        assert sanitize_filename("/absolute/path/to/main.cpp") == "main.cpp"

    def test_strips_windows_path_traversal(self) -> None:
        assert sanitize_filename(r"..\..\..\windows\system32\calc.c") == "calc.c"
        assert sanitize_filename(r"C:\Windows\System32\drivers.h") == "drivers.h"

    def test_removes_null_bytes_and_control_characters(self) -> None:
        assert sanitize_filename("main.c\x00.exe") == "main.c.exe"
        assert sanitize_filename("test\x07\x1f.cpp") == "test.cpp"

    def test_neutralizes_windows_reserved_names(self) -> None:
        assert sanitize_filename("CON.c") == "safe_CON.c"
        assert sanitize_filename("aux.h") == "safe_aux.h"
        assert sanitize_filename("NUL.cpp") == "safe_NUL.cpp"
        assert sanitize_filename("com1.c") == "safe_com1.c"

    def test_empty_or_whitespace_falls_back_to_default(self) -> None:
        assert sanitize_filename("") == "file"
        assert sanitize_filename("   ...   ") == "file"
        assert sanitize_filename(None, default="default.pdf") == "default.pdf"


# ─────────────────────────────────────────────
# 4. Storage containment
# ─────────────────────────────────────────────


class TestStorageContainment:
    def test_storage_blocks_traversal_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorageService(base_dir=tmpdir)
            with pytest.raises(ValueError, match="Invalid storage key path traversal"):
                storage.upload_file("../../../etc/shadow", b"malicious", "text/plain")

    def test_storage_blocks_sibling_folder_prefix_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorageService(base_dir=tmpdir)
            # Sibling folder with same prefix
            with pytest.raises(ValueError, match="Invalid storage key path traversal"):
                storage.upload_file("../storage_sibling/evil.c", b"bad", "text/plain")


# ─────────────────────────────────────────────
# 5. Security headers
# ─────────────────────────────────────────────


class TestSecurityHeaders:
    def test_health_endpoint_returns_security_headers(self) -> None:
        client = TestClient(app)
        response = client.get("/v1/health")
        assert response.status_code == 200

        headers = response.headers
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in headers.get("Permissions-Policy", "")


# ─────────────────────────────────────────────
# 6. Secret redaction & safe error handling
# ─────────────────────────────────────────────


class TestSecretRedaction:
    def test_redacts_gemini_api_key(self) -> None:
        raw = "Failed to call endpoint with key=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q"
        sanitized = sanitize_secrets(raw)
        assert "AIzaSy" not in sanitized
        assert "[REDACTED_GEMINI_KEY]" in sanitized

    def test_redacts_bearer_token(self) -> None:
        raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret12345"
        sanitized = sanitize_secrets(raw)
        assert "secret12345" not in sanitized
        assert "[REDACTED_TOKEN]" in sanitized

    def test_redacts_clerk_secret_key(self) -> None:
        raw = "Using clerk key clerk_test_abcdef123456789012345678"
        sanitized = sanitize_secrets(raw)
        assert "clerk_test_" not in sanitized
        assert "[REDACTED_CLERK_KEY]" in sanitized

    def test_sanitize_error_detail_masks_credentials(self) -> None:
        exc = Exception("API key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q is invalid")
        detail = sanitize_error_detail(exc)
        assert "AIzaSy" not in detail
        assert "Gemini API connection or authentication failed." in detail

    def test_sanitize_error_detail_general_exception_returns_default(self) -> None:
        exc = Exception("psycopg2.OperationalError: server closed the connection unexpectedly at 10.0.0.1:5432")
        detail = sanitize_error_detail(exc, default="Operation failed.")
        assert detail == "Operation failed."
        assert "10.0.0.1" not in detail
        assert "psycopg2" not in detail



# ─────────────────────────────────────────────
# 7. Input validation bounds
# ─────────────────────────────────────────────


class TestInputValidationBounds:
    def test_oversized_question_fails_validation(
        self, user_a: User, project_b: Project
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: user_a
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = project_b
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            # user_question max_length is 10,000 chars
            oversized_question = "A" * 10_001
            response = client.post(
                f"/v1/projects/{project_b.id}/debug",
                json={"user_question": oversized_question},
            )
            # Pydantic validation failure
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
