import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.debug_message import DebugMessage
from app.models.debug_session import DebugSession
from app.models.feedback import Feedback
from app.models.project import Project
from app.models.user import User
from app.schemas.debug import DebugResponse


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        clerk_id="user_clerk_sessions",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Test Project",
        description="Test",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


MOCK_DIAGNOSIS = DebugResponse(
    problem_observed="Test problem",
    evidence_used=["evidence 1"],
    likely_causes=[{"cause": "test cause", "plausibility": "high"}],
    recommended_steps=["step 1"],
    proposed_fix="test fix",
    corrected_code="int main() {}",
    risks_limitations=None,
    follow_up_required=None,
)


def test_create_session_calls_ai_and_persists(
    mock_user: User, mock_project: Project
) -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_project

    # Simulate commit by populating the session via refresh
    def fake_refresh(obj: object) -> None:
        if isinstance(obj, DebugSession):
            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)
            # Simulate lazy-loaded messages
            obj.messages = []  # type: ignore[attr-defined]

    mock_db.refresh.side_effect = fake_refresh

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        with patch("app.routers.sessions.analyze_debugging_context", return_value=MOCK_DIAGNOSIS):
            response = client.post(
                f"/v1/projects/{mock_project.id}/sessions",
                json={
                    "title": "My Debug Session",
                    "firmware_code": "void setup() {}",
                    "compiler_output": "error: missing ;",
                    "serial_logs": "",
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Debug Session"
        assert data["project_id"] == str(mock_project.id)
        # 3 domain adds: session + user message + assistant message
        from app.models.analytics_event import AnalyticsEvent
        domain_adds = [c for c in mock_db.add.call_args_list if not isinstance(c.args[0], AnalyticsEvent)]
        assert len(domain_adds) == 3
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_list_sessions(mock_user: User, mock_project: Project) -> None:
    mock_db = MagicMock()

    session_1 = DebugSession(
        id=uuid.uuid4(),
        project_id=mock_project.id,
        user_id=mock_user.id,
        title="Session 1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # First filter call returns project, second returns sessions list
    mock_query = MagicMock()
    call_count = [0]

    def fake_filter(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.first.return_value = mock_project
        else:
            result.order_by.return_value.all.return_value = [session_1]
        return result

    mock_db.query.return_value.filter.side_effect = fake_filter

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{mock_project.id}/sessions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Session 1"
    finally:
        app.dependency_overrides.clear()


def test_get_session_detail(mock_user: User, mock_project: Project) -> None:
    session_id = uuid.uuid4()
    msg = DebugMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="assistant",
        content='{"problem_observed": "test"}',
        created_at=datetime.now(UTC),
    )
    session = DebugSession(
        id=session_id,
        project_id=mock_project.id,
        user_id=mock_user.id,
        title="Detail Session",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.messages = [msg]  # type: ignore[assignment]

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, session]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{mock_project.id}/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Detail Session"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "assistant"
    finally:
        app.dependency_overrides.clear()


def test_delete_session(mock_user: User, mock_project: Project) -> None:
    session_id = uuid.uuid4()
    session = DebugSession(
        id=session_id,
        project_id=mock_project.id,
        user_id=mock_user.id,
        title="To Delete",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, session]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.delete(f"/v1/projects/{mock_project.id}/sessions/{session_id}")
        assert response.status_code == 204
        assert mock_db.delete.called
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_session_not_found(mock_user: User, mock_project: Project) -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, None]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get(
            f"/v1/projects/{mock_project.id}/sessions/{uuid.uuid4()}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found"
    finally:
        app.dependency_overrides.clear()
