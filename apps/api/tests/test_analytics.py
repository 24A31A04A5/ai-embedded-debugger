"""Tests for Phase 6.3 — Analytics & Product Metrics."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.analytics_event import AnalyticsEvent
from app.models.project import Project
from app.models.user import User
from app.schemas.analytics import AnalyticsEventType
from app.schemas.debug import DebugResponse, LikelyCause
from app.services.analytics import AnalyticsService, sanitize_analytics_metadata
from app.services.storage import BaseStorageService, get_storage_service


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
        email="analytics_tester@example.com",
        clerk_id="user_clerk_analytics_1",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="other_user@example.com",
        clerk_id="user_clerk_analytics_2",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Analytics Project",
        description="Workspace for analytics verification",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def in_memory_storage() -> InMemoryStorageService:
    return InMemoryStorageService()


# ─────────────────────────────────────────────
# 1. Analytics Service Unit Tests
# ─────────────────────────────────────────────


class TestAnalyticsServiceUnit:
    def test_sanitize_metadata_removes_sensitive_data(self) -> None:
        """Sensitive fields (code, logs, tokens, secrets, prompts) must be stripped."""
        raw = {
            "file_type": "c",
            "size_bytes": 1024,
            "firmware_code": "void secret_algorithm() {}",
            "serial_logs": "Crash at 0x4000: fatal error",
            "compiler_output": "error: undeclared identifier",
            "user_question": "Why is my secret token leaking?",
            "api_key": "sk-1234567890",
            "client_token": "bearer xyz",
            "db_password": "supersecretpassword",
            "safe_metric": 42,
        }
        cleaned = sanitize_analytics_metadata(raw)
        assert cleaned is not None
        assert "firmware_code" not in cleaned
        assert "serial_logs" not in cleaned
        assert "compiler_output" not in cleaned
        assert "user_question" not in cleaned
        assert "api_key" not in cleaned
        assert "client_token" not in cleaned
        assert "db_password" not in cleaned
        assert cleaned["file_type"] == "c"
        assert cleaned["size_bytes"] == 1024
        assert cleaned["safe_metric"] == 42

    def test_sanitize_metadata_truncates_long_strings(self) -> None:
        raw = {"safe_note": "A" * 500}
        cleaned = sanitize_analytics_metadata(raw)
        assert cleaned is not None
        assert len(cleaned["safe_note"]) < 300
        assert cleaned["safe_note"].endswith("...")

    def test_track_event_persists_when_enabled(self) -> None:
        mock_db = MagicMock(spec=Session)
        uid = uuid.uuid4()
        pid = uuid.uuid4()

        event = AnalyticsService.track_event(
            mock_db,
            AnalyticsEventType.DEBUG_REQUEST_COMPLETED,
            user_id=uid,
            project_id=pid,
            latency_ms=123,
            metadata={"confidence_level": "high"},
        )

        assert event is not None
        assert event.event_type == AnalyticsEventType.DEBUG_REQUEST_COMPLETED.value
        assert event.user_id == uid
        assert event.project_id == pid
        assert event.latency_ms == 123
        assert event.metadata_json == {"confidence_level": "high"}
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_track_event_disabled_bypasses_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANALYTICS_ENABLED", "false")
        get_settings.cache_clear()
        mock_db = MagicMock(spec=Session)

        try:
            event = AnalyticsService.track_event(
                mock_db,
                AnalyticsEventType.DEBUG_REQUEST_COMPLETED,
                metadata={"test": "data"},
            )
            assert event is None
            assert not mock_db.add.called
            assert not mock_db.commit.called
        finally:
            get_settings.cache_clear()

    def test_track_event_failure_never_raises(self) -> None:
        """Database errors during event logging must never bubble up."""
        mock_db = MagicMock(spec=Session)
        mock_db.commit.side_effect = RuntimeError("Database connection lost")

        # Must not raise
        result = AnalyticsService.track_event(
            mock_db,
            AnalyticsEventType.DEBUG_REQUEST_STARTED,
        )
        assert result is None
        assert mock_db.rollback.called

    def test_get_project_summary_aggregation(self) -> None:
        mock_db = MagicMock(spec=Session)
        pid = uuid.uuid4()
        uid = uuid.uuid4()

        mock_events = [
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.DEBUG_REQUEST_STARTED.value,
                project_id=pid,
                user_id=uid,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.DEBUG_REQUEST_COMPLETED.value,
                project_id=pid,
                user_id=uid,
                latency_ms=100,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.DEBUG_REQUEST_COMPLETED.value,
                project_id=pid,
                user_id=uid,
                latency_ms=200,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.DEBUG_REQUEST_FAILED.value,
                project_id=pid,
                user_id=uid,
                latency_ms=50,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.FILE_UPLOADED.value,
                project_id=pid,
                user_id=uid,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.DOCUMENT_UPLOADED.value,
                project_id=pid,
                user_id=uid,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.SESSION_CREATED.value,
                project_id=pid,
                user_id=uid,
            ),
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.FEEDBACK_SUBMITTED.value,
                project_id=pid,
                user_id=uid,
                metadata_json={"rating": 1},
            ),
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = mock_events

        summary = AnalyticsService.get_project_summary(mock_db, project_id=pid)

        assert summary.project_id == pid
        assert summary.total_debug_requests == 1
        assert summary.successful_debug_requests == 2
        assert summary.failed_debug_requests == 1
        assert summary.avg_debug_latency_ms == 150.0  # (100 + 200) / 2
        assert summary.total_files_uploaded == 1
        assert summary.total_documents_uploaded == 1
        assert summary.total_sessions_created == 1
        assert summary.feedback_count == 1
        assert summary.positive_feedback_count == 1
        assert summary.event_counts[AnalyticsEventType.DEBUG_REQUEST_COMPLETED.value] == 2


# ─────────────────────────────────────────────
# 2. Router Integration Tests
# ─────────────────────────────────────────────


class TestAnalyticsRouterIntegrations:
    def test_debug_endpoint_tracks_lifecycle(
        self, mock_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch("app.routers.debug.analyze_debugging_context") as mock_ai, patch.object(
                AnalyticsService, "track_event", wraps=AnalyticsService.track_event
            ) as spy_track:
                mock_ai.return_value = DebugResponse(
                    problem_observed="OK",
                    evidence_used=["line 1"],
                    likely_causes=[LikelyCause(cause="none", plausibility="high")],
                    recommended_steps=["step 1"],
                    proposed_fix="none",
                )

                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={"firmware_code": "void loop() {}", "user_question": "Status?"},
                )
                assert response.status_code == 200

                # Both started and completed events should be called
                event_types_called = [call[0][1] for call in spy_track.call_args_list]
                assert AnalyticsEventType.DEBUG_REQUEST_STARTED in event_types_called
                assert AnalyticsEventType.DEBUG_REQUEST_COMPLETED in event_types_called

                # Verify metadata passed does NOT contain raw code
                for call in spy_track.call_args_list:
                    meta = call[1].get("metadata") or {}
                    assert "void loop()" not in str(meta)
                    assert "Status?" not in str(meta)
        finally:
            app.dependency_overrides.clear()

    def test_debug_endpoint_tracks_failure_event(
        self, mock_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch(
                "app.routers.debug.analyze_debugging_context",
                side_effect=ValueError("Model unavailable"),
            ), patch.object(AnalyticsService, "track_event", wraps=AnalyticsService.track_event) as spy_track:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={"user_question": "help"},
                )
                assert response.status_code == 500

                event_types_called = [call[0][1] for call in spy_track.call_args_list]
                assert AnalyticsEventType.DEBUG_REQUEST_STARTED in event_types_called
                assert AnalyticsEventType.DEBUG_REQUEST_FAILED in event_types_called
        finally:
            app.dependency_overrides.clear()

    def test_file_upload_tracks_event(
        self,
        mock_user: User,
        mock_project: Project,
        in_memory_storage: InMemoryStorageService,
    ) -> None:
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
            with patch.object(AnalyticsService, "track_event", wraps=AnalyticsService.track_event) as spy_track:
                r = client.post(
                    f"/v1/projects/{mock_project.id}/files/upload",
                    files={"file": ("main.c", io.BytesIO(b"int main() { return 0; }"), "text/x-c")},
                )
                assert r.status_code == 201

                event_types_called = [call[0][1] for call in spy_track.call_args_list]
                assert AnalyticsEventType.FILE_UPLOADED in event_types_called
        finally:
            app.dependency_overrides.clear()

    def test_feedback_submission_tracks_event(
        self, mock_user: User, mock_project: Project
    ) -> None:
        from app.models.debug_session import DebugSession

        session_id = uuid.uuid4()
        fake_session = DebugSession(
            id=session_id,
            project_id=mock_project.id,
            user_id=mock_user.id,
            title="Session 1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            fake_session,
            None,  # no existing feedback
        ]

        from app.models.feedback import Feedback

        def fake_refresh(obj: object) -> None:
            if isinstance(obj, Feedback):
                obj.created_at = datetime.now(UTC)

        mock_db.refresh.side_effect = fake_refresh

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            with patch.object(AnalyticsService, "track_event", wraps=AnalyticsService.track_event) as spy_track:
                r = client.post(
                    f"/v1/sessions/{session_id}/feedback",
                    json={"rating": 1, "reason": "Useful answer"},
                )
                assert r.status_code == 201

                event_types_called = [call[0][1] for call in spy_track.call_args_list]
                assert AnalyticsEventType.FEEDBACK_SUBMITTED in event_types_called
        finally:
            app.dependency_overrides.clear()


# ─────────────────────────────────────────────
# 3. Project Analytics Endpoint Authorization & Output
# ─────────────────────────────────────────────


class TestProjectAnalyticsEndpoint:
    def test_owner_can_retrieve_project_analytics(
        self, mock_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project
        mock_db.query.return_value.filter.return_value.all.return_value = [
            AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=AnalyticsEventType.DEBUG_REQUEST_COMPLETED.value,
                project_id=mock_project.id,
                user_id=mock_user.id,
                latency_ms=180,
                created_at=datetime.now(UTC),
            )
        ]

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.get(f"/v1/projects/{mock_project.id}/analytics?days=14")
            assert response.status_code == 200
            data = response.json()
            assert data["project_id"] == str(mock_project.id)
            assert data["time_window_days"] == 14
            assert data["successful_debug_requests"] == 1
            assert data["avg_debug_latency_ms"] == 180.0
        finally:
            app.dependency_overrides.clear()

    def test_non_owner_cannot_retrieve_project_analytics(
        self, other_user: User, mock_project: Project
    ) -> None:
        mock_db = MagicMock()
        # Owner filter returns None because other_user != owner
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: other_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.get(f"/v1/projects/{mock_project.id}/analytics")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
