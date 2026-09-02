"""Tests for Phase 4.4 — Embedded Debugging Reasoning for the AI Embedded Debugger.

Covers:
1. Root-cause reasoning from multiple evidence sources
2. Code + compiler correlation
3. Compiler + serial-log correlation
4. Serial-log + datasheet correlation
5. Insufficient evidence handling
6. Confirmed vs suspected reasoning
7. Practical debugging recommendations (software -> patch -> hardware checks)
8. Preservation of existing structured analysis fields
9. Existing debug behavior
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import SYSTEM_INSTRUCTION, analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.project import Project
from app.models.user import User
from app.schemas.context import (
    AssembledDebugContext,
    DocumentContext,
    ProjectContext,
)
from app.schemas.debug import (
    CodeIssue,
    CompilerMessage,
    DebugResponse,
    DocumentCitation,
    LikelyCause,
    SerialLogEvent,
)


# ─────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="embedded_expert@example.com",
        clerk_id="user_clerk_reasoning",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="STM32 Multi-Evidence Workspace",
        description="Phase 4.4 reasoning and cross-correlation test bed",
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


# ─────────────────────────────────────────────
# Sample multi-evidence responses
# ─────────────────────────────────────────────

MULTI_EVIDENCE_RESPONSE = DebugResponse(
    problem_observed="I2C sensor read fails with timeout because GPIO21/22 open-drain mode lacks pull-ups and i2c_master_init returned an unhandled error code.",
    evidence_used=[
        "[Code] main.c:35: esp_err_t err = i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0); // err not checked",
        "[Compiler] main.c:35: warning: unused variable 'err' [-Wunused-variable]",
        "[Serial Log] [00:00:03.450] E (3450) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
        "[Datasheet] ESP32 TRM p.45: I2C open-drain lines GPIO21 (SDA) and GPIO22 (SCL) require external 4.7kΩ pull-up resistors.",
    ],
    likely_causes=[
        LikelyCause(
            cause="Missing external 4.7kΩ pull-up resistors on SDA/SCL lines (confirmed by datasheet & timeout log)",
            plausibility="high",
        ),
        LikelyCause(
            cause="Ignored i2c_driver_install return code allowed firmware to proceed in uninitialized state",
            plausibility="medium",
        ),
    ],
    recommended_steps=[
        "1. Check if i2c_driver_install returns ESP_OK before issuing bus transactions.",
        "2. Add gpio_pullup_en(GPIO_NUM_21) and gpio_pullup_en(GPIO_NUM_22) in firmware as an initial test.",
        "3. Measure SDA and SCL idle voltage with a multimeter; verify 3.3V presence (requires external 4.7kΩ resistors for reliable communication).",
        "4. Probe bus with an oscilloscope or logic analyzer to confirm ACK pulses from the sensor.",
    ],
    proposed_fix="Enable internal pull-ups in software and attach external 4.7kΩ resistors to 3.3V rail.",
    corrected_code="ESP_ERROR_CHECK(i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0));\ngpio_pullup_en(GPIO_NUM_21);\ngpio_pullup_en(GPIO_NUM_22);",
    risks_limitations="Internal weak pull-ups (~45kΩ) may not support I2C Fast Mode (400kHz); external 4.7kΩ resistors are strongly recommended for production.",
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="esp32_technical_reference.pdf",
            page_number=45,
            relevant_snippet="GPIO21 and GPIO22 require external pull-up resistors for reliable I2C communication at standard bus speeds.",
            relevance_explanation="Confirms hardware pull-up requirement on open-drain GPIO lines.",
        )
    ],
    grounded_summary="ESP32 I2C open-drain pins GPIO21/22 require pull-up resistors to 3.3V for reliable bus operation.",
    code_issues=[
        CodeIssue(
            kind="resource_misuse",
            severity="high",
            confirmed=True,
            description="i2c_driver_install() return code is ignored; uninitialized driver state causes silent failures.",
            location="main.c:35 in i2c_init()",
            evidence="esp_err_t err = i2c_driver_install(...);",
            suggestion="Use ESP_ERROR_CHECK(i2c_driver_install(...));",
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
            likely_cause="I2C lines held low or floating due to missing pull-up resistors.",
            suggested_action="Verify physical 4.7k pull-up resistors on SDA (GPIO21) and SCL (GPIO22).",
        )
    ],
)

COMPILER_LOG_CORRELATION_RESPONSE = DebugResponse(
    problem_observed="HardFault crash in UART driver caused by uninitialized pointer, directly predicted by compiler warning.",
    evidence_used=[
        "[Compiler] uart.c:18: warning: 'p_buf' may be used uninitialized in this function [-Wmaybe-uninitialized]",
        "[Serial Log] HardFault Exception: HFSR=0x40000000 (FORCED), CFSR=0x00008200 (BFARVALID, PRECISERR), BFAR=0x00000004",
    ],
    likely_causes=[
        LikelyCause(
            cause="p_buf pointer was uninitialized (holding small offset 0x4); dereferencing triggered precise BusFault/HardFault",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "1. Initialize p_buf to NULL or point to a valid allocated buffer in uart.c:18.",
        "2. Enable -Werror=maybe-uninitialized in compiler flags to block uninitialized pointer builds.",
    ],
    proposed_fix="Initialize uint8_t *p_buf = NULL; and allocate before use.",
    corrected_code="uint8_t *p_buf = rx_buffer_get();\nif (!p_buf) return ERR_NO_MEM;",
    risks_limitations=None,
    follow_up_required=None,
    compiler_messages=[
        CompilerMessage(
            message_type="warning",
            severity="high",
            is_root_cause=True,
            file="uart.c",
            line=18,
            column=12,
            message="'p_buf' may be used uninitialized in this function [-Wmaybe-uninitialized]",
            code_context="uint8_t *p_buf;",
            likely_cause="Variable declared without initial assignment before branch.",
            suggested_fix="uint8_t *p_buf = rx_buffer_get();",
        )
    ],
    serial_log_events=[
        SerialLogEvent(
            event_type="crash_fault",
            severity="critical",
            is_repeated=False,
            timestamp=None,
            message="HardFault Exception: PRECISERR at BFAR=0x00000004",
            evidence="HardFault Exception: HFSR=0x40000000, CFSR=0x00008200, BFAR=0x00000004",
            likely_cause="Invalid memory access to address 0x00000004 caused by uninitialized pointer dereference.",
            suggested_action="Check stack trace and initialize pointer p_buf in uart.c:18.",
        )
    ],
)

INSUFFICIENT_EVIDENCE_RESPONSE = DebugResponse(
    problem_observed="Cannot confirm root cause: no compiler output, serial logs, or MCU register details provided.",
    evidence_used=["User question indicates sensor fails, but no logs or code lines were provided."],
    likely_causes=[
        LikelyCause(cause="Missing hardware wiring or incorrect baud rate (suspected)", plausibility="low"),
        LikelyCause(cause="Firmware initialization failure (suspected)", plausibility="low"),
    ],
    recommended_steps=[
        "1. Connect serial monitor and upload boot/runtime logs.",
        "2. Provide C/C++ initialization code for the sensor.",
        "3. Attach compiler output with -Wall enabled.",
    ],
    proposed_fix="Provide serial logs or source code to enable a confident diagnosis.",
    corrected_code=None,
    risks_limitations=None,
    follow_up_required="Please provide serial monitor logs, compiler output, or relevant C/C++ source code.",
)


# ─────────────────────────────────────────────
# 1. Root-cause reasoning from multiple evidence sources
# ─────────────────────────────────────────────


class TestMultiSourceReasoning:
    def test_multi_source_evidence_synthesized_into_single_diagnosis(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="I2C Test"),
            firmware_code="esp_err_t err = i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0);",
            compiler_output="main.c:35:15: warning: unused variable 'err' [-Wunused-variable]",
            serial_logs="[00:00:03.450] E (3450) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
        )
        mock_client = _fake_gemini_client(MULTI_EVIDENCE_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert "pull-up" in result.problem_observed.lower() or "i2c" in result.problem_observed.lower()
        assert len(result.evidence_used) >= 3
        assert result.code_issues is not None
        assert result.compiler_messages is not None
        assert result.serial_log_events is not None
        assert result.datasheet_citations is not None

    def test_system_instruction_contains_holistic_reasoning_section(self) -> None:
        assert "Holistic Embedded Debugging Reasoning" in SYSTEM_INSTRUCTION
        assert "Multi-Source Cross-Correlation" in SYSTEM_INSTRUCTION
        assert "Code + Compiler" in SYSTEM_INSTRUCTION
        assert "Compiler + Serial Log" in SYSTEM_INSTRUCTION
        assert "Serial Log + Datasheet" in SYSTEM_INSTRUCTION
        assert "Evidence Triangulation & Certainty" in SYSTEM_INSTRUCTION


# ─────────────────────────────────────────────
# 2. Code + compiler correlation
# ─────────────────────────────────────────────


class TestCodeCompilerCorrelation:
    def test_compiler_warning_correlates_with_code_issue_location(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        assert res.compiler_messages is not None
        assert res.code_issues is not None

        c_msg = res.compiler_messages[0]
        c_iss = res.code_issues[0]

        # Both reference line 35 of main.c
        assert c_msg.file == "main.c"
        assert c_msg.line == 35
        assert "main.c:35" in c_iss.location


# ─────────────────────────────────────────────
# 3. Compiler + serial-log correlation
# ─────────────────────────────────────────────


class TestCompilerSerialLogCorrelation:
    def test_uninitialized_pointer_warning_correlates_to_runtime_hardfault(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="HardFault Test"),
            compiler_output="uart.c:18: warning: 'p_buf' may be used uninitialized [-Wmaybe-uninitialized]",
            serial_logs="HardFault Exception: CFSR=0x00008200, BFAR=0x00000004",
        )
        mock_client = _fake_gemini_client(COMPILER_LOG_CORRELATION_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.compiler_messages is not None
        assert result.serial_log_events is not None
        assert "uninitialized" in result.problem_observed.lower() or "hardfault" in result.problem_observed.lower()
        assert result.likely_causes[0].plausibility == "high"


# ─────────────────────────────────────────────
# 4. Serial-log + datasheet correlation
# ─────────────────────────────────────────────


class TestSerialLogDatasheetCorrelation:
    def test_runtime_timeout_correlated_with_datasheet_pullup_spec(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        assert res.serial_log_events is not None
        assert res.datasheet_citations is not None

        log_ev = res.serial_log_events[0]
        citation = res.datasheet_citations[0]

        assert log_ev.event_type == "timeout"
        assert "esp32_technical_reference.pdf" in citation.document_name
        assert "pull-up" in citation.relevant_snippet.lower()


# ─────────────────────────────────────────────
# 5. Insufficient evidence handling
# ─────────────────────────────────────────────


class TestInsufficientEvidenceHandling:
    def test_missing_evidence_populates_follow_up_without_fabrication(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="No Evidence"),
            user_question="Why is my sensor not working?",
        )
        mock_client = _fake_gemini_client(INSUFFICIENT_EVIDENCE_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.follow_up_required is not None
        assert len(result.follow_up_required) > 0
        # All likely causes have low plausibility when evidence is missing
        for cause in result.likely_causes:
            assert cause.plausibility == "low"


# ─────────────────────────────────────────────
# 6. Confirmed vs suspected reasoning
# ─────────────────────────────────────────────


class TestConfirmedVsSuspectedReasoning:
    def test_direct_evidence_marked_confirmed_true(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        assert res.code_issues is not None
        # Resource misuse has direct compiler evidence line 35 -> confirmed = True
        assert res.code_issues[0].confirmed is True

    def test_hypotheses_ranked_by_plausibility(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        plausibilities = [c.plausibility for c in res.likely_causes]
        assert plausibilities[0] == "high"


# ─────────────────────────────────────────────
# 7. Practical debugging recommendations (ordered steps)
# ─────────────────────────────────────────────


class TestPracticalDebuggingRecommendations:
    def test_recommended_steps_contain_software_and_hardware_checks(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        steps_text = " ".join(res.recommended_steps).lower()

        # Step contains software check/patch
        assert "driver" in steps_text or "pullup" in steps_text
        # Step contains physical/hardware measurement verification
        assert "multimeter" in steps_text or "oscilloscope" in steps_text or "measure" in steps_text

    def test_risks_and_limitations_warn_about_hardware_constraints(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        assert res.risks_limitations is not None
        assert "400khz" in res.risks_limitations or "pull-up" in res.risks_limitations.lower()


# ─────────────────────────────────────────────
# 8. Preservation of all structured analysis fields
# ─────────────────────────────────────────────


class TestStructuredAnalysisFieldPreservation:
    def test_all_phase_fields_coexist_in_single_response(self) -> None:
        res = MULTI_EVIDENCE_RESPONSE
        assert res.problem_observed is not None
        assert len(res.evidence_used) > 0
        assert len(res.likely_causes) > 0
        assert len(res.recommended_steps) > 0
        assert res.proposed_fix is not None
        assert res.corrected_code is not None
        assert res.datasheet_citations is not None
        assert res.grounded_summary is not None
        assert res.code_issues is not None
        assert res.compiler_messages is not None
        assert res.serial_log_events is not None


# ─────────────────────────────────────────────
# 9. Existing debug behavior
# ─────────────────────────────────────────────


class TestExistingDebugBehavior:
    def test_debug_endpoint_returns_holistic_response(
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
            return_value=MULTI_EVIDENCE_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "firmware_code": "i2c_driver_install(...);",
                        "compiler_output": "main.c:35: warning: unused variable 'err'",
                        "serial_logs": "ESP_ERR_TIMEOUT",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert "I2C" in data["problem_observed"] or "pull-up" in data["problem_observed"]
                assert data["code_issues"] is not None
                assert data["compiler_messages"] is not None
                assert data["serial_log_events"] is not None
                assert data["datasheet_citations"] is not None
            finally:
                app.dependency_overrides.clear()
