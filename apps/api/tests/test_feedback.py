import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.debug_session import DebugSession
from app.models.feedback import Feedback
from app.models.user import User


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="feedback_user@example.com",
        clerk_id="user_clerk_fb",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_session(mock_user: User) -> DebugSession:
    return DebugSession(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        user_id=mock_user.id,
        title="Feedback Test Session",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_submit_feedback(mock_user: User, mock_session: DebugSession) -> None:
    mock_db = MagicMock()
    # First query = session lookup, second query = existing feedback check
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_session,
        None,  # no existing feedback
    ]

    def fake_refresh(obj: object) -> None:
        if isinstance(obj, Feedback):
            obj.created_at = datetime.now(UTC)

    mock_db.refresh.side_effect = fake_refresh

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/sessions/{mock_session.id}/feedback",
            json={"rating": 1, "reason": "Very helpful!"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 1
        assert data["reason"] == "Very helpful!"
        assert data["session_id"] == str(mock_session.id)
        assert mock_db.add.called
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_update_existing_feedback(mock_user: User, mock_session: DebugSession) -> None:
    existing_feedback = Feedback(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        session_id=mock_session.id,
        rating=1,
        reason="Was good",
        created_at=datetime.now(UTC),
    )
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_session,
        existing_feedback,
    ]

    def fake_refresh(obj: object) -> None:
        pass

    mock_db.refresh.side_effect = fake_refresh

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/sessions/{mock_session.id}/feedback",
            json={"rating": 0, "reason": "Changed my mind"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 0
        assert data["reason"] == "Changed my mind"
        # Should update, not add new
        assert not mock_db.add.called
    finally:
        app.dependency_overrides.clear()


def test_get_feedback(mock_user: User, mock_session: DebugSession) -> None:
    existing_feedback = Feedback(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        session_id=mock_session.id,
        rating=1,
        reason="Great",
        created_at=datetime.now(UTC),
    )
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_feedback

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get(f"/v1/sessions/{mock_session.id}/feedback")
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 1
    finally:
        app.dependency_overrides.clear()


def test_get_feedback_none(mock_user: User, mock_session: DebugSession) -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get(f"/v1/sessions/{mock_session.id}/feedback")
        assert response.status_code == 200
        assert response.json() is None
    finally:
        app.dependency_overrides.clear()


def test_feedback_session_not_found(mock_user: User) -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/sessions/{uuid.uuid4()}/feedback",
            json={"rating": 1},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found"
    finally:
        app.dependency_overrides.clear()
