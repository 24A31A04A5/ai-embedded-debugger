import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.debug_message import DebugMessage
from app.models.debug_session import DebugSession
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.schemas.context import (
    AssembledDebugContext,
    DocumentContext,
    ProjectContext,
    UploadedFileContext,
)
from app.schemas.debug import DebugResponse
from app.services.context_assembly import ContextAssemblyService
from app.services.storage import BaseStorageService, get_storage_service


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="dev@example.com",
        clerk_id="user_clerk_ctx",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="other@example.com",
        clerk_id="user_other",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Context Project",
        description="Firmware Debugging Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def other_project(other_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=other_user.id,
        name="Other User Project",
        description="Other Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


MOCK_DIAGNOSIS = DebugResponse(
    problem_observed="Null pointer dereference",
    evidence_used=["main.c line 42: ptr is NULL before access"],
    likely_causes=[{"cause": "Uninitialized pointer", "plausibility": "high"}],
    recommended_steps=["Initialize ptr before use or check for NULL"],
    proposed_fix="Add if (!ptr) return; guard",
    corrected_code="if (ptr) { ptr->field = 1; }",
    risks_limitations=None,
    follow_up_required=None,
)


def test_context_assembled_from_pasted_code_and_logs(
    mock_user: User, mock_project: Project
) -> None:
    """Context assembly properly structures pasted code, compiler output, and serial logs."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    ctx = service.assemble_context(
        project_id=mock_project.id,
        current_user=mock_user,
        firmware_code="void loop() { int x = 1; }",
        compiler_output="warning: unused variable x",
        serial_logs="[LOG] Starting task...",
        user_question="Why is variable x unused?",
    )

    assert isinstance(ctx, AssembledDebugContext)
    assert ctx.project.project_name == "ESP32 Context Project"
    assert ctx.project.project_id == mock_project.id
    assert ctx.user_question == "Why is variable x unused?"
    assert "void loop()" in ctx.firmware_code
    assert "unused variable x" in ctx.compiler_output
    assert "[LOG] Starting task..." in ctx.serial_logs
    assert ctx.is_truncated is False
    assert len(ctx.uploaded_files) == 0

    prompt = ctx.format_prompt()
    assert "<project_context>" in prompt
    assert "<user_question>" in prompt
    assert "<firmware_code>" in prompt
    assert "<compiler_output>" in prompt
    assert "<serial_logs>" in prompt


def test_context_assembled_with_selected_uploaded_file(
    mock_user: User, mock_project: Project
) -> None:
    """Context assembly retrieves file content from storage and includes file metadata."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    file_id = uuid.uuid4()
    db_file = ProjectFile(
        id=file_id,
        project_id=mock_project.id,
        filename="driver.c",
        file_type="code",
        size_bytes=120,
        checksum="abc123",
        storage_key=f"projects/{mock_project.id}/files/{file_id}_driver.c",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    mock_db.query.return_value.filter.return_value.all.return_value = [db_file]
    mock_storage.get_file.return_value = b"#include <driver.h>\nvoid init_gpio() {}"

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    ctx = service.assemble_context(
        project_id=mock_project.id,
        current_user=mock_user,
        firmware_code="int main() {}",
        selected_file_ids=[file_id],
    )

    assert len(ctx.uploaded_files) == 1
    file_ctx = ctx.uploaded_files[0]
    assert file_ctx.file_id == file_id
    assert file_ctx.filename == "driver.c"
    assert file_ctx.file_type == "code"
    assert "#include <driver.h>" in file_ctx.content
    assert file_ctx.is_truncated is False

    prompt = ctx.format_prompt()
    assert '<file id="' in prompt
    assert 'name="driver.c"' in prompt
    assert "void init_gpio()" in prompt


def test_context_assembled_with_multiple_selected_files(
    mock_user: User, mock_project: Project
) -> None:
    """Multiple uploaded files are retrieved and assembled with individual metadata."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    file_id1 = uuid.uuid4()
    file_id2 = uuid.uuid4()

    db_file1 = ProjectFile(
        id=file_id1,
        project_id=mock_project.id,
        filename="sensor.h",
        file_type="code",
        size_bytes=50,
        checksum="hash1",
        storage_key="key1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_file2 = ProjectFile(
        id=file_id2,
        project_id=mock_project.id,
        filename="uart_crash.log",
        file_type="log",
        size_bytes=80,
        checksum="hash2",
        storage_key="key2",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    mock_db.query.return_value.filter.return_value.all.return_value = [db_file1, db_file2]

    def mock_get(key: str) -> bytes:
        if key == "key1":
            return b"int read_temp();"
        return b"[ERROR] UART buffer overflow"

    mock_storage.get_file.side_effect = mock_get

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    ctx = service.assemble_context(
        project_id=mock_project.id,
        current_user=mock_user,
        selected_file_ids=[file_id1, file_id2],
    )

    assert len(ctx.uploaded_files) == 2
    assert ctx.uploaded_files[0].filename == "sensor.h"
    assert ctx.uploaded_files[1].filename == "uart_crash.log"
    assert "read_temp" in ctx.uploaded_files[0].content
    assert "UART buffer overflow" in ctx.uploaded_files[1].content


def test_project_ownership_isolation(mock_user: User, other_project: Project) -> None:
    """Accessing files or projects of another user raises 404."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    # User does not own other_project
    mock_db.query.return_value.filter.return_value.first.return_value = None

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    with pytest.raises(HTTPException) as exc_info:
        service.assemble_context(
            project_id=other_project.id,
            current_user=mock_user,
            firmware_code="int x;",
        )

    assert exc_info.value.status_code == 404
    assert "Project not found" in exc_info.value.detail


def test_missing_file_handling(mock_user: User, mock_project: Project) -> None:
    """Missing or unauthorized file ID raises a 404."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    # No files found in DB
    mock_db.query.return_value.filter.return_value.all.return_value = []

    missing_id = uuid.uuid4()
    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    with pytest.raises(HTTPException) as exc_info:
        service.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            selected_file_ids=[missing_id],
        )

    assert exc_info.value.status_code == 404
    assert "Project file not found" in exc_info.value.detail


def test_missing_storage_file_handling(mock_user: User, mock_project: Project) -> None:
    """If file is in DB but missing from storage, a 404 is raised."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    file_id = uuid.uuid4()
    db_file = ProjectFile(
        id=file_id,
        project_id=mock_project.id,
        filename="config.h",
        file_type="code",
        size_bytes=10,
        checksum="hash",
        storage_key="missing_key",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    mock_db.query.return_value.filter.return_value.all.return_value = [db_file]
    mock_storage.get_file.side_effect = FileNotFoundError("Storage file not found")

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    with pytest.raises(HTTPException) as exc_info:
        service.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            selected_file_ids=[file_id],
        )

    assert exc_info.value.status_code == 404
    assert "missing in storage" in exc_info.value.detail


def test_context_truncation_limits(mock_user: User, mock_project: Project) -> None:
    """Large file and text inputs are truncated with clear notices."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    file_id = uuid.uuid4()
    db_file = ProjectFile(
        id=file_id,
        project_id=mock_project.id,
        filename="huge_firmware.c",
        file_type="code",
        size_bytes=1000,
        checksum="hash",
        storage_key="huge_key",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    mock_db.query.return_value.filter.return_value.all.return_value = [db_file]

    huge_file_content = "X" * 500
    mock_storage.get_file.return_value = huge_file_content.encode("utf-8")

    # Set very small limits for testing
    service = ContextAssemblyService(
        db=mock_db,
        storage=mock_storage,
        max_file_chars=50,
        max_text_chars=60,
    )

    huge_compiler_out = "E" * 200
    ctx = service.assemble_context(
        project_id=mock_project.id,
        current_user=mock_user,
        compiler_output=huge_compiler_out,
        selected_file_ids=[file_id],
    )

    assert ctx.is_truncated is True
    assert len(ctx.truncation_notes) == 2
    assert ctx.uploaded_files[0].is_truncated is True
    assert ctx.uploaded_files[0].truncated_length == 50
    assert ctx.uploaded_files[0].original_length == 500
    assert len(ctx.compiler_output) == 60

    prompt = ctx.format_prompt()
    assert "<context_limits_notice>" in prompt
    assert "[TRUNCATED from 500 chars]" in prompt


def test_session_history_context_assembly(
    mock_user: User, mock_project: Project
) -> None:
    """Previous session history is assembled chronologically into context."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    session_id = uuid.uuid4()
    db_session = DebugSession(
        id=session_id,
        project_id=mock_project.id,
        user_id=mock_user.id,
        title="Prior Session",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    msg1 = DebugMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="user",
        content="I have a memory leak in heap_caps_malloc",
        created_at=datetime.now(UTC),
    )
    msg2 = DebugMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="assistant",
        content='{"problem_observed": "Leak detected"}',
        created_at=datetime.now(UTC),
    )

    # First filter returns project, second returns session
    def fake_filter(*args, **kwargs):  # type: ignore[no-untyped-def]
        mock_res = MagicMock()
        if not hasattr(fake_filter, "calls"):
            fake_filter.calls = 0  # type: ignore[attr-defined]
        fake_filter.calls += 1  # type: ignore[attr-defined]

        if fake_filter.calls == 1:  # type: ignore[attr-defined]
            mock_res.first.return_value = mock_project
        elif fake_filter.calls == 2:  # type: ignore[attr-defined]
            mock_res.first.return_value = db_session
        else:
            mock_res.order_by.return_value.limit.return_value.all.return_value = [
                msg2,
                msg1,
            ]
        return mock_res

    mock_db.query.return_value.filter.side_effect = fake_filter

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    ctx = service.assemble_context(
        project_id=mock_project.id,
        current_user=mock_user,
        firmware_code="void test() {}",
        session_id=session_id,
    )

    assert len(ctx.session_history) == 2
    assert ctx.session_history[0].role == "user"
    assert "memory leak" in ctx.session_history[0].content
    assert ctx.session_history[1].role == "assistant"

    prompt = ctx.format_prompt()
    assert "<session_history>" in prompt
    assert "[USER]: I have a memory leak" in prompt


def test_empty_optional_inputs(mock_user: User, mock_project: Project) -> None:
    """Empty optional inputs assemble without crashing or generating unnecessary prompt blocks."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project

    service = ContextAssemblyService(db=mock_db, storage=mock_storage)
    ctx = service.assemble_context(
        project_id=mock_project.id,
        current_user=mock_user,
    )

    assert ctx.firmware_code == ""
    assert ctx.compiler_output == ""
    assert ctx.serial_logs == ""
    assert len(ctx.uploaded_files) == 0
    assert len(ctx.session_history) == 0
    assert len(ctx.document_context) == 0

    prompt = ctx.format_prompt()
    assert "<project_context>" in prompt
    assert "<firmware_code>" not in prompt
    assert "<compiler_output>" not in prompt
    assert "<serial_logs>" not in prompt
    assert "<uploaded_files>" not in prompt
    assert "<session_history>" not in prompt


def test_debug_endpoint_with_context_assembly(
    mock_user: User, mock_project: Project
) -> None:
    """The /v1/projects/{project_id}/debug endpoint runs ContextAssemblyService and AI analysis."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        with patch(
            "app.routers.debug.analyze_debugging_context", return_value=MOCK_DIAGNOSIS
        ) as mock_ai:
            response = client.post(
                f"/v1/projects/{mock_project.id}/debug",
                json={
                    "firmware_code": "int *p = NULL; *p = 10;",
                    "compiler_output": "",
                    "serial_logs": "Guru Meditation Error: Core 0 panic'ed",
                    "user_question": "Why did my ESP32 panic?",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["problem_observed"] == "Null pointer dereference"
            assert mock_ai.called
            # Verify that analyze_debugging_context was passed an AssembledDebugContext instance
            passed_arg = mock_ai.call_args[0][0]
            assert isinstance(passed_arg, AssembledDebugContext)
            assert passed_arg.user_question == "Why did my ESP32 panic?"
            assert "Guru Meditation" in passed_arg.serial_logs
    finally:
        app.dependency_overrides.clear()
