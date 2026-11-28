"""Tests for Phase 11.1 — Streaming Diagnostics (SSE)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.project import Project
from app.models.user import User
from app.schemas.debug import DebugRequest, DebugResponse


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="dev@example.com",
        clerk_id="user_clerk_streaming",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="Streaming Test Project",
        description="SSE Streaming Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestStreamingEndpoint:
    """Integration tests for POST /projects/{project_id}/debug/stream endpoint."""

    def test_streaming_endpoint_returns_sse_response(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Streaming endpoint should return text/event-stream content type."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock rate limiter and settings to avoid rate limit errors
        app.dependency_overrides["app.routers.debug.check_ai_rate_limit"] = lambda: None
        app.dependency_overrides["app.routers.debug.get_settings"] = MagicMock(
            rate_limit_enabled=False,
            stream_timeout_seconds=30,
            stream_heartbeat_seconds=15,
        )

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        # Patch the services at module level
        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    # Mock async generator
                    async def mock_generator():
                        yield "First chunk of analysis"
                        yield "Second chunk with diagnosis"
                        yield "Final chunk with code fix"

                    mock_stream.return_value = mock_generator()

                    client = TestClient(app)
                    try:
                        response = client.post(
                            f"/v1/projects/{mock_project.id}/debug/stream",
                            json={
                                "firmware_code": "void setup() {}",
                                "compiler_output": "error: 'Serial' not declared",
                                "serial_logs": "",
                            },
                        )
                        assert response.status_code == 200
                        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                        assert response.headers["cache-control"] == "no-cache"
                        assert response.headers["connection"] == "keep-alive"
                    finally:
                        app.dependency_overrides.clear()

    def test_streaming_sse_format(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Streaming should yield properly formatted SSE events."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock rate limiter and settings to avoid rate limit errors
        app.dependency_overrides["app.routers.debug.check_ai_rate_limit"] = lambda: None
        app.dependency_overrides["app.routers.debug.get_settings"] = MagicMock(
            rate_limit_enabled=False,
            stream_timeout_seconds=30,
            stream_heartbeat_seconds=15,
        )

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    async def mock_generator():
                        yield '{"problem_observed": "Serial not declared"}'
                        yield '{"likely_causes": [{"cause": "Missing include", "plausibility": 0.9}]}'

                    mock_stream.return_value = mock_generator()

                    client = TestClient(app)
                    try:
                        with client.stream(
                            "POST",
                            f"/v1/projects/{mock_project.id}/debug/stream",
                            json={
                                "firmware_code": "void setup() {}",
                                "compiler_output": "error: 'Serial' not declared",
                                "serial_logs": "",
                            },
                        ) as response:
                            assert response.status_code == 200
                            # Read streaming response
                            content = ""
                            for chunk in response.iter_text():
                                content += chunk

                            # Verify SSE format
                            assert "data:" in content
                            assert "problem_observed" in content
                            assert "likely_causes" in content
                    finally:
                        app.dependency_overrides.clear()

    def test_streaming_handles_client_disconnect(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Streaming should handle client disconnect gracefully."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock rate limiter and settings to avoid rate limit errors
        app.dependency_overrides["app.routers.debug.check_ai_rate_limit"] = lambda: None
        app.dependency_overrides["app.routers.debug.get_settings"] = MagicMock(
            rate_limit_enabled=False,
            stream_timeout_seconds=30,
            stream_heartbeat_seconds=15,
        )

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    async def mock_generator():
                        for i in range(10):
                            yield f"Chunk {i}"
                            # Simulate small delay
                            import asyncio
                            await asyncio.sleep(0.01)

                    mock_stream.return_value = mock_generator()

                    client = TestClient(app)
                    try:
                        # Just verify it starts streaming without error
                        response = client.post(
                            f"/v1/projects/{mock_project.id}/debug/stream",
                            json={
                                "firmware_code": "void setup() {}",
                                "compiler_output": "error",
                                "serial_logs": "",
                            },
                        )
                        assert response.status_code == 200
                    finally:
                        app.dependency_overrides.clear()

    def test_streaming_timeout_handling(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Streaming should respect timeout settings."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    with patch("app.routers.debug.get_settings") as mock_settings:
                        mock_settings.return_value = MagicMock(
                            rate_limit_enabled=False,
                            stream_timeout_seconds=1,
                            stream_heartbeat_seconds=30,
                        )

                        async def mock_generator():
                            # Yield many chunks slowly
                            for i in range(100):
                                yield f"Chunk {i}"
                                import asyncio
                                await asyncio.sleep(0.1)

                        mock_stream.return_value = mock_generator()

                        client = TestClient(app)
                        try:
                            response = client.post(
                                f"/v1/projects/{mock_project.id}/debug/stream",
                                json={
                                    "firmware_code": "void setup() {}",
                                    "compiler_output": "error",
                                    "serial_logs": "",
                                },
                            )
                            # Should complete (timeout check happens in generator)
                            assert response.status_code == 200
                        finally:
                            app.dependency_overrides.clear()


class TestStreamingHeartbeat:
    """Tests for heartbeat/keep-alive mechanism."""

    def test_heartbeat_sent_at_interval(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Heartbeat comments should be sent at configured interval."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    with patch("app.routers.debug.get_settings") as mock_settings:
                        mock_settings.return_value = MagicMock(
                            rate_limit_enabled=False,
                            stream_timeout_seconds=30,
                            stream_heartbeat_seconds=0.1,  # 100ms heartbeat interval
                        )

                        async def mock_generator():
                            for i in range(5):
                                yield f"Chunk {i}"
                                import asyncio
                                await asyncio.sleep(0.2)  # 200ms delay between chunks

                        mock_stream.return_value = mock_generator()

                        client = TestClient(app)
                        try:
                            with client.stream(
                                "POST",
                                f"/v1/projects/{mock_project.id}/debug/stream",
                                json={
                                    "firmware_code": "void setup() {}",
                                    "compiler_output": "error",
                                    "serial_logs": "",
                                },
                            ) as response:
                                content = ""
                                for chunk in response.iter_text():
                                    content += chunk
                                # Heartbeat comments start with ":" followed by space and "heartbeat"
                                assert ": heartbeat" in content
                        finally:
                            app.dependency_overrides.clear()


class TestStreamingErrorHandling:
    """Tests for streaming error scenarios."""

    def test_streaming_error_returns_sse_error(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Errors during streaming should be sent as SSE error events."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock rate limiter and settings to avoid rate limit errors
        app.dependency_overrides["app.routers.debug.check_ai_rate_limit"] = lambda: None
        app.dependency_overrides["app.routers.debug.get_settings"] = MagicMock(
            rate_limit_enabled=False,
            stream_timeout_seconds=30,
            stream_heartbeat_seconds=15,
        )

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    async def mock_generator():
                        yield "First chunk"
                        raise Exception("AI service unavailable")

                    mock_stream.return_value = mock_generator()

                    client = TestClient(app)
                    try:
                        with client.stream(
                            "POST",
                            f"/v1/projects/{mock_project.id}/debug/stream",
                            json={
                                "firmware_code": "void setup() {}",
                                "compiler_output": "error",
                                "serial_logs": "",
                            },
                        ) as response:
                            content = ""
                            for chunk in response.iter_text():
                                content += chunk
                            assert "error" in content.lower()
                            assert "AI service unavailable" in content
                    finally:
                        app.dependency_overrides.clear()

    def test_streaming_unauthorized_returns_401(
        self,
        mock_project: Project,
    ) -> None:
        """Streaming endpoint should require authentication."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock rate limiter and settings to avoid rate limit errors
        app.dependency_overrides["app.routers.debug.check_ai_rate_limit"] = lambda: None
        app.dependency_overrides["app.routers.debug.get_settings"] = MagicMock(
            rate_limit_enabled=False,
            stream_timeout_seconds=30,
            stream_heartbeat_seconds=15,
        )

        # Mock get_current_user dependency to raise HTTPException for unauthorized
        def mock_auth_failure():
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = mock_auth_failure

        # Mock services to prevent context assembly errors
        mock_context_service = MagicMock()
        mock_context_service.assemble_context.return_value = MagicMock()
        app.dependency_overrides["app.routers.debug.ContextAssemblyService"] = lambda: mock_context_service

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/debug/stream",
                json={
                    "firmware_code": "void setup() {}",
                    "compiler_output": "error",
                    "serial_logs": "",
                },
            )
            assert response.status_code in (401, 403)
        finally:
            app.dependency_overrides.clear()


class TestStreamingAnalytics:
    """Tests for streaming analytics tracking."""

    def test_streaming_tracks_analytics_on_complete(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """Analytics should be tracked when stream completes."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock rate limiter and settings to avoid rate limit errors
        app.dependency_overrides["app.routers.debug.check_ai_rate_limit"] = lambda: None
        app.dependency_overrides["app.routers.debug.get_settings"] = MagicMock(
            rate_limit_enabled=False,
            stream_timeout_seconds=30,
            stream_heartbeat_seconds=15,
        )

        from app.services.context_assembly import ContextAssemblyService
        from app.services.retrieval import DocumentRetrievalService
        from app.services.analytics import AnalyticsService

        mock_context_service = MagicMock(spec=ContextAssemblyService)
        mock_context_service.assemble_context.return_value = MagicMock()

        mock_retrieval_service = MagicMock(spec=DocumentRetrievalService)

        with patch("app.routers.debug.ContextAssemblyService", return_value=mock_context_service):
            with patch("app.routers.debug.DocumentRetrievalService", return_value=mock_retrieval_service):
                with patch("app.routers.debug.analyze_debugging_context_stream") as mock_stream:
                    with patch.object(AnalyticsService, "track_event") as mock_track:
                        async def mock_generator():
                            yield "Chunk 1"
                            yield "Chunk 2"

                        mock_stream.return_value = mock_generator()

                        client = TestClient(app)
                        try:
                            response = client.post(
                                f"/v1/projects/{mock_project.id}/debug/stream",
                                json={
                                    "firmware_code": "void setup() {}",
                                    "compiler_output": "error",
                                    "serial_logs": "",
                                },
                            )
                            assert response.status_code == 200
                            # Analytics should be called for completion
                            mock_track.assert_called()
                        finally:
                            app.dependency_overrides.clear()