import io
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.services.storage import BaseStorageService, get_storage_service


class InMemoryStorageService(BaseStorageService):
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def upload_file(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self.store[storage_key] = data

    def get_file(self, storage_key: str) -> bytes:
        if storage_key not in self.store:
            raise FileNotFoundError(f"Key {storage_key} not found")
        return self.store[storage_key]

    def delete_file(self, storage_key: str) -> None:
        self.store.pop(storage_key, None)

    def get_download_url(self, storage_key: str, expires_in: int = 3600) -> str | None:
        return f"http://mock-storage/{storage_key}"


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        clerk_id="user_clerk_123",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Debug Workspace",
        description="Test description",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def in_memory_storage() -> InMemoryStorageService:
    return InMemoryStorageService()


def test_upload_file_success(
    mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService
) -> None:
    mock_db = MagicMock()

    # Separate mock chains for Project (first) and ProjectFile (count)
    def _query_side_effect(model_class):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model_class.__name__ == "Project":
            f.first.return_value = mock_project
        else:  # ProjectFile quota check
            f.count.return_value = 0
        return q

    mock_db.query.side_effect = _query_side_effect

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

    client = TestClient(app)
    try:
        file_content = b"#include <stdio.h>\nvoid setup() {}"
        response = client.post(
            f"/v1/projects/{mock_project.id}/files/upload",
            files={"file": ("main.c", io.BytesIO(file_content), "text/x-c")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "main.c"
        assert data["file_type"] == "code"
        assert data["size_bytes"] == len(file_content)
        assert data["download_url"] is not None
        assert mock_db.add.called
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_upload_disallowed_extension(
    mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService
) -> None:
    mock_db = MagicMock()

    def _query_side_effect(model_class):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model_class.__name__ == "Project":
            f.first.return_value = mock_project
        else:
            f.count.return_value = 0
        return q

    mock_db.query.side_effect = _query_side_effect

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/projects/{mock_project.id}/files/upload",
            files={"file": ("malicious.exe", io.BytesIO(b"binary"), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported file extension" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_list_files(
    mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService
) -> None:
    mock_db = MagicMock()
    mock_filter = MagicMock()
    mock_db.query.return_value.filter.return_value = mock_filter
    mock_filter.first.return_value = mock_project

    file_1 = ProjectFile(
        id=uuid.uuid4(),
        project_id=mock_project.id,
        filename="firmware.ino",
        file_type="code",
        size_bytes=1024,
        checksum="dummyhash",
        storage_key="projects/123/files/abc_firmware.ino",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    # mock order_by.all for project_files query
    mock_filter.order_by.return_value.all.return_value = [file_1]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{mock_project.id}/files")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "firmware.ino"
    finally:
        app.dependency_overrides.clear()


def test_get_file_content(
    mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService
) -> None:
    mock_db = MagicMock()
    file_id = uuid.uuid4()
    storage_key = f"projects/{mock_project.id}/files/{file_id}_main.cpp"
    in_memory_storage.upload_file(storage_key, b"int main() { return 42; }")

    file_record = ProjectFile(
        id=file_id,
        project_id=mock_project.id,
        filename="main.cpp",
        file_type="code",
        size_bytes=25,
        checksum="hash123",
        storage_key=storage_key,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # First query is project check, second query is file check
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, file_record]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{mock_project.id}/files/{file_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["filename"] == "main.cpp"
        assert data["content"] == "int main() { return 42; }"
    finally:
        app.dependency_overrides.clear()


def test_delete_file(
    mock_user: User, mock_project: Project, in_memory_storage: InMemoryStorageService
) -> None:
    mock_db = MagicMock()
    file_id = uuid.uuid4()
    storage_key = f"projects/{mock_project.id}/files/{file_id}_serial.log"
    in_memory_storage.upload_file(storage_key, b"Booting ESP32...")

    file_record = ProjectFile(
        id=file_id,
        project_id=mock_project.id,
        filename="serial.log",
        file_type="log",
        size_bytes=16,
        checksum="hashlog",
        storage_key=storage_key,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, file_record]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

    client = TestClient(app)
    try:
        response = client.delete(f"/v1/projects/{mock_project.id}/files/{file_id}")
        assert response.status_code == 204
        assert storage_key not in in_memory_storage.store
        assert mock_db.delete.called
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_project_not_found_or_unauthorized(
    mock_user: User, in_memory_storage: InMemoryStorageService
) -> None:
    mock_db = MagicMock()
    # Project query returns None (not found or not owned by user)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: in_memory_storage

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{uuid.uuid4()}/files")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"
    finally:
        app.dependency_overrides.clear()
