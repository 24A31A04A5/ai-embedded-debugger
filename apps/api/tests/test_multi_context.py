"""Tests for Phase 4.6 — Multi-Context Debugging for the AI Embedded Debugger.

Covers:
1. Code + compiler + serial logs together
2. Code + compiler + RAG together
3. All available context sources together (code, compiler, logs, files, session history, RAG, project)
4. Missing / partial context handled gracefully
5. Context size / truncation behavior and budget limits
6. Previous session context integration
7. Ownership and project isolation
8. Preservation of all structured response fields
9. Existing debug endpoint and session creation behavior
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.ai.gemini import analyze_debugging_context
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
    SessionHistoryItem,
    UploadedFileContext,
)
from app.schemas.debug import (
    CodeIssue,
    CompilerMessage,
    DebugResponse,
    DocumentCitation,
    LikelyCause,
    SerialLogEvent,
)
from app.schemas.document import DocumentSearchResultItem
from app.services.context_assembly import ContextAssemblyService
from app.services.retrieval import DocumentRetrievalService


# ─────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="multicontext_dev@example.com",
        clerk_id="user_clerk_multicontext",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="intruder@example.com",
        clerk_id="user_clerk_intruder",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Multi-Context Workspace",
        description="Comprehensive testing for Phase 4.6",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def other_project(other_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=other_user.id,
        name="Private Workspace",
        description="Should not be accessible",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _fake_gemini_client(response_obj: DebugResponse) -> MagicMock:
    """Return a mock genai.Client whose generate_content produces response_obj."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = response_obj.model_dump_json()
    mock_client.models.generate_content.return_value = mock_resp
    return mock_client


ALL_CONTEXT_RESPONSE = DebugResponse(
    problem_observed="I2C sensor communication failure: bus timeout in driver caused by missing external pull-up resistors and uninitialized driver return code.",
    root_cause_summary="Missing 4.7kΩ pull-up resistors on GPIO21/22 and unchecked error return from i2c_driver_install.",
    confidence_level="high",
    evidence_used=[
        "[Code] main.c:35: esp_err_t err = i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0);",
        "[Compiler] main.c:35: warning: unused variable 'err' [-Wunused-variable]",
        "[Serial Log] [00:00:03.450] E (3450) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
        "[Uploaded File] include/bme280.h: #define BME280_I2C_ADDR 0x76",
        "[Prior Session] USER: Why is my sensor returning 0xFF?",
        "[Datasheet] ESP32 TRM p.45: GPIO21 (SDA) and GPIO22 (SCL) require external 4.7kΩ pull-up resistors.",
    ],
    likely_causes=[
        LikelyCause(
            cause="Open-drain GPIO21/22 pins lack external 4.7kΩ pull-up resistors (confirmed by TRM & timeout)",
            plausibility="high",
        ),
        LikelyCause(
            cause="Unchecked i2c_driver_install return code allowed execution with uninitialized I2C peripheral",
            plausibility="medium",
        ),
    ],
    recommended_steps=[
        "1. Check if i2c_driver_install returns ESP_OK before issuing transactions.",
        "2. Add gpio_pullup_en(GPIO_NUM_21) and gpio_pullup_en(GPIO_NUM_22) in firmware.",
        "3. Measure SDA and SCL idle voltage with a multimeter; verify 3.3V presence.",
    ],
    proposed_fix="Add return code verification and enable pull-ups.",
    corrected_code="ESP_ERROR_CHECK(i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0));\ngpio_pullup_en(GPIO_NUM_21);\ngpio_pullup_en(GPIO_NUM_22);",
    risks_limitations="Internal weak pull-ups may be insufficient for high-speed I2C modes (>100kHz).",
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="esp32_technical_reference.pdf",
            page_number=45,
            relevant_snippet="GPIO21 and GPIO22 require external pull-up resistors for reliable I2C operation.",
            relevance_explanation="Confirms open-drain pull-up requirement.",
        )
    ],
    grounded_summary="ESP32 I2C open-drain lines require external pull-up resistors to 3.3V.",
    code_issues=[
        CodeIssue(
            kind="resource_misuse",
            severity="high",
            confirmed=True,
            description="Unchecked return code from driver installation.",
            location="main.c:35",
            evidence="esp_err_t err = i2c_driver_install(...);",
            suggestion="Use ESP_ERROR_CHECK(err);",
        )
    ],
    compiler_messages=[
        CompilerMessage(
            message_type="warning",
            severity="medium",
            is_root_cause=False,
            file="main.c",
            line=35,
            column=15,
            message="unused variable 'err' [-Wunused-variable]",
            code_context="esp_err_t err = i2c_driver_install(...);",
            likely_cause="Return value assigned to variable but never checked.",
            suggested_fix="ESP_ERROR_CHECK(err);",
        )
    ],
    serial_log_events=[
        SerialLogEvent(
            event_type="timeout",
            severity="high",
            is_repeated=False,
            timestamp="00:00:03.450",
            message="i2c_master_write returned ESP_ERR_TIMEOUT",
            evidence="[00:00:03.450] E (3450) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
            likely_cause="Missing pull-up resistors or sensor unacknowledged.",
            suggested_action="Verify physical 4.7kΩ pull-up resistors on SDA/SCL lines.",
        )
    ],
)


# ─────────────────────────────────────────────
# 1. Code + compiler + serial logs together
# ─────────────────────────────────────────────


class TestCodeCompilerSerialLogsTogether:
    def test_prompt_formatting_includes_code_compiler_and_serial_sections(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Trio Test"),
            firmware_code="void setup() { Wire.begin(); }",
            compiler_output="main.c:2: warning: Wire is deprecated",
            serial_logs="[00:01:00] E: Timeout waiting for device",
        )
        prompt = ctx.format_prompt()
        assert "<firmware_code>" in prompt
        assert "Wire.begin()" in prompt
        assert "<compiler_output>" in prompt
        assert "Wire is deprecated" in prompt
        assert "<serial_logs>" in prompt
        assert "Timeout waiting for device" in prompt


# ─────────────────────────────────────────────
# 2. Code + compiler + RAG together
# ─────────────────────────────────────────────


class TestCodeCompilerRagTogether:
    def test_prompt_formatting_includes_code_compiler_and_datasheet_chunks(self) -> None:
        doc = DocumentContext(
            chunk_id=str(uuid.uuid4()),
            doc_id=str(uuid.uuid4()),
            title="esp32_tr_manual.pdf",
            snippet="Pin 21 is SDA, Pin 22 is SCL.",
            page_number=45,
            score=0.92,
        )
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="RAG Trio Test"),
            firmware_code="i2c_set_pin(0, 21, 22, true, true, I2C_MODE_MASTER);",
            compiler_output="main.c:1: error: expected identifier",
            document_context=[doc],
        )
        prompt = ctx.format_prompt()
        assert "<firmware_code>" in prompt
        assert "<compiler_output>" in prompt
        assert "<retrieved_datasheets_and_documents>" in prompt
        assert 'document="esp32_tr_manual.pdf"' in prompt
        assert 'page="45"' in prompt
        assert "Pin 21 is SDA" in prompt


# ─────────────────────────────────────────────
# 3. All available context sources together
# ─────────────────────────────────────────────


class TestAllAvailableContextSourcesTogether:
    def test_full_context_assembly_and_prompt_generation(self) -> None:
        file_ctx = UploadedFileContext(
            file_id=uuid.uuid4(),
            filename="bme280.h",
            file_type="code",
            size_bytes=100,
            content="#define BME280_I2C_ADDR 0x76",
        )
        hist_item = SessionHistoryItem(
            session_id=uuid.uuid4(),
            role="user",
            content="Why is my sensor returning 0xFF?",
        )
        doc = DocumentContext(
            chunk_id=str(uuid.uuid4()),
            title="esp32_technical_reference.pdf",
            snippet="GPIO21 and GPIO22 require external pull-up resistors.",
            page_number=45,
        )
        ctx = AssembledDebugContext(
            project=ProjectContext(
                project_id=uuid.uuid4(),
                project_name="Complete Context Project",
                description="Testing all 8 context streams",
            ),
            user_question="Why does my I2C read fail?",
            firmware_code="esp_err_t err = i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0);",
            compiler_output="main.c:35: warning: unused variable 'err'",
            serial_logs="[00:00:03.450] E (3450) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
            uploaded_files=[file_ctx],
            session_history=[hist_item],
            document_context=[doc],
        )

        prompt = ctx.format_prompt()

        # Check all 8 XML sections present
        assert "<project_context>" in prompt
        assert "Complete Context Project" in prompt
        assert "<user_question>" in prompt
        assert "Why does my I2C read fail?" in prompt
        assert "<firmware_code>" in prompt
        assert "i2c_driver_install" in prompt
        assert "<compiler_output>" in prompt
        assert "unused variable 'err'" in prompt
        assert "<serial_logs>" in prompt
        assert "ESP_ERR_TIMEOUT" in prompt
        assert "<uploaded_files>" in prompt
        assert 'name="bme280.h"' in prompt
        assert "<session_history>" in prompt
        assert "Why is my sensor returning 0xFF?" in prompt
        assert "<retrieved_datasheets_and_documents>" in prompt
        assert "GPIO21 and GPIO22 require external pull-up resistors" in prompt

    def test_gemini_analysis_with_all_contexts_returns_complete_diagnosis(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Full Context"),
            user_question="Diagnose my I2C problem",
            firmware_code="Wire.begin();",
        )
        mock_client = _fake_gemini_client(ALL_CONTEXT_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.confidence_level == "high"
        assert result.root_cause_summary is not None
        assert result.code_issues is not None
        assert result.compiler_messages is not None
        assert result.serial_log_events is not None
        assert result.datasheet_citations is not None


# ─────────────────────────────────────────────
# 4. Missing / partial context handled gracefully
# ─────────────────────────────────────────────


class TestPartialContextHandling:
    def test_only_user_question_provided(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Only Question"),
            user_question="What is the default I2C clock on ESP32?",
        )
        prompt = ctx.format_prompt()
        assert "<user_question>" in prompt
        assert "<firmware_code>" not in prompt
        assert "<compiler_output>" not in prompt
        assert "<serial_logs>" not in prompt
        assert "<uploaded_files>" not in prompt
        assert "<session_history>" not in prompt
        assert "<retrieved_datasheets_and_documents>" not in prompt

    def test_only_serial_logs_provided(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Only Logs"),
            serial_logs="[00:00:01.000] Brownout detector was triggered",
        )
        prompt = ctx.format_prompt()
        assert "<serial_logs>" in prompt
        assert "Brownout detector" in prompt
        assert "<firmware_code>" not in prompt
        assert "<compiler_output>" not in prompt


# ─────────────────────────────────────────────
# 5. Context size / truncation behavior
# ─────────────────────────────────────────────


class TestContextSizeAndTruncation:
    def test_budget_truncation_adds_notice(self, mock_user: User, mock_project: Project) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        # Set small text limit (100 chars)
        svc = ContextAssemblyService(db=mock_db, max_text_chars=100)
        long_code = "int x = 1;\n" * 50  # ~550 chars

        context = svc.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            firmware_code=long_code,
        )

        assert context.is_truncated is True
        assert len(context.truncation_notes) >= 1
        assert len(context.firmware_code) <= 100

        prompt = context.format_prompt()
        assert "<context_limits_notice>" in prompt
        assert "truncated from" in prompt


# ─────────────────────────────────────────────
# 6. Previous session context integration
# ─────────────────────────────────────────────


class TestPreviousSessionContextIntegration:
    def test_session_history_loaded_and_ordered_chronologically(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        session_id = uuid.uuid4()
        db_session = DebugSession(
            id=session_id,
            project_id=mock_project.id,
            user_id=mock_user.id,
            title="Initial Discussion",
        )

        msg1 = DebugMessage(
            id=uuid.uuid4(),
            session_id=session_id,
            role="user",
            content="First question",
            created_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        )
        msg2 = DebugMessage(
            id=uuid.uuid4(),
            session_id=session_id,
            role="assistant",
            content="First answer",
            created_at=datetime(2026, 1, 1, 10, 1, 0, tzinfo=UTC),
        )

        mock_db = MagicMock()
        # First query for Project
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project
        # Query for DebugSession
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = db_session
        # Query for DebugMessage (returned in desc order, reversed by assembly service)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [msg2, msg1]

        svc = ContextAssemblyService(db=mock_db)
        context = svc.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            session_id=session_id,
            user_question="Follow up question",
        )

        assert len(context.session_history) == 2
        # Chronological order
        assert context.session_history[0].content == "First question"
        assert context.session_history[1].content == "First answer"

        prompt = context.format_prompt()
        assert "<session_history>" in prompt
        assert "[USER]: First question" in prompt
        assert "[ASSISTANT]: First answer" in prompt


# ─────────────────────────────────────────────
# 7. Ownership and project isolation
# ─────────────────────────────────────────────


class TestOwnershipAndIsolation:
    def test_assemble_context_for_unauthorized_project_raises_404(
        self,
        mock_user: User,
        other_project: Project,
    ) -> None:
        mock_db = MagicMock()
        # Project not found or owner_id != mock_user.id
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = ContextAssemblyService(db=mock_db)
        with pytest.raises(HTTPException) as exc_info:
            svc.assemble_context(
                project_id=other_project.id,
                current_user=mock_user,
                firmware_code="void setup() {}",
            )
        assert exc_info.value.status_code == 404
        assert "Project not found" in exc_info.value.detail


# ─────────────────────────────────────────────
# 8. Preservation of all structured response fields
# ─────────────────────────────────────────────


class TestStructuredResponsePreservation:
    def test_all_phase_fields_intact_in_full_multi_context_response(self) -> None:
        res = ALL_CONTEXT_RESPONSE
        # Phase 4.5 fields
        assert res.root_cause_summary is not None
        assert res.confidence_level == "high"
        # Phase 4.1 field
        assert res.code_issues is not None
        assert len(res.code_issues) == 1
        # Phase 4.2 field
        assert res.compiler_messages is not None
        assert len(res.compiler_messages) == 1
        # Phase 4.3 field
        assert res.serial_log_events is not None
        assert len(res.serial_log_events) == 1
        # Phase 3.4 fields
        assert res.datasheet_citations is not None
        assert len(res.datasheet_citations) == 1
        assert res.grounded_summary is not None


# ─────────────────────────────────────────────
# 9. Existing debug behavior (Endpoint and Session Creation)
# ─────────────────────────────────────────────


class TestExistingDebugEndpoints:
    def test_debug_endpoint_multi_context_analysis(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.routers.debug.analyze_debugging_context",
            return_value=ALL_CONTEXT_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "firmware_code": "esp_err_t err = i2c_driver_install(...);",
                        "compiler_output": "main.c:35: warning: unused variable 'err'",
                        "serial_logs": "[00:00:03.450] E (3450) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
                        "user_question": "Why is I2C failing?",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["problem_observed"] == ALL_CONTEXT_RESPONSE.problem_observed
                assert data["root_cause_summary"] == ALL_CONTEXT_RESPONSE.root_cause_summary
                assert data["confidence_level"] == "high"
                assert data["code_issues"] is not None
                assert data["compiler_messages"] is not None
                assert data["serial_log_events"] is not None
                assert data["datasheet_citations"] is not None
            finally:
                app.dependency_overrides.clear()

    def test_session_creation_persists_multi_context_metadata(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        def fake_refresh(obj: object) -> None:
            if isinstance(obj, DebugSession):
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)
                obj.messages = []  # type: ignore[attr-defined]

        mock_db.refresh.side_effect = fake_refresh

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.routers.sessions.analyze_debugging_context",
            return_value=ALL_CONTEXT_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/sessions",
                    json={
                        "title": "Comprehensive I2C Session",
                        "firmware_code": "i2c_driver_install(...);",
                        "compiler_output": "warning: unused variable 'err'",
                        "serial_logs": "ESP_ERR_TIMEOUT",
                        "user_question": "Why does I2C timeout?",
                    },
                )
                assert response.status_code == 201
                data = response.json()
                assert data["title"] == "Comprehensive I2C Session"
                assert mock_db.add.called
                assert mock_db.commit.called
            finally:
                app.dependency_overrides.clear()
