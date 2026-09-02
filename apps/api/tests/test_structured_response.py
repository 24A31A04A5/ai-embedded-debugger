"""Tests for Phase 4.5 — Structured Debug Response for the AI Embedded Debugger.

Covers:
1. Complete structured response with all fields
2. All analysis fields coexisting simultaneously
3. Missing/optional fields handled safely
4. Confidence/evidence handling
5. Grounded citations schema & traceability
6. Malformed and empty AI response handling
7. Backward compatibility with older/minimal DebugResponse objects
8. Existing debug endpoint integration
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import analyze_debugging_context
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
        email="structured_qa@example.com",
        clerk_id="user_clerk_structured",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="Structured Debug Project",
        description="Phase 4.5 structured response verification",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _fake_gemini_client(response_obj: DebugResponse | str) -> MagicMock:
    """Return a mock genai.Client whose generate_content produces response_obj."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    if isinstance(response_obj, str):
        mock_resp.text = response_obj
    else:
        mock_resp.text = response_obj.model_dump_json()
    mock_client.models.generate_content.return_value = mock_resp
    return mock_client


# ─────────────────────────────────────────────
# Sample full structured response fixture
# ─────────────────────────────────────────────

COMPLETE_DEBUG_RESPONSE = DebugResponse(
    problem_observed="I2C bus timeout and HardFault crash during BME280 sensor initialization.",
    root_cause_summary="Missing 4.7kΩ pull-up resistors on GPIO21/22 and unchecked NULL return from malloc.",
    confidence_level="high",
    evidence_used=[
        "[Code] main.c:18: uint8_t *buf = malloc(256); buf[0] = 0; // unchecked malloc",
        "[Compiler] main.c:35: warning: unused variable 'err' [-Wunused-variable]",
        "[Serial Log] Guru Meditation Error: Core 0 panic'ed (LoadProhibited) at PC 0x400d1234",
        "[Datasheet] ESP32 TRM p.45: I2C open-drain lines require external pull-up resistors.",
    ],
    likely_causes=[
        LikelyCause(
            cause="Unchecked malloc() in main.c returned NULL, triggering LoadProhibited panic",
            plausibility="high",
        ),
        LikelyCause(
            cause="Open-drain I2C lines lack external 4.7kΩ pull-up resistors to 3.3V rail",
            plausibility="high",
        ),
    ],
    recommended_steps=[
        "1. Check if buf == NULL after malloc() in main.c:18 before dereferencing.",
        "2. Add gpio_pullup_en(GPIO_NUM_21) and gpio_pullup_en(GPIO_NUM_22) in firmware initialization.",
        "3. Measure SDA and SCL idle voltage with a multimeter; verify 3.3V presence.",
        "4. Probe bus with an oscilloscope or logic analyzer to verify I2C ACK pulses.",
    ],
    proposed_fix="Add NULL pointer validation and attach external pull-up resistors to the I2C bus.",
    corrected_code=(
        "uint8_t *buf = malloc(256);\n"
        "if (!buf) {\n"
        "    ESP_LOGE(TAG, \"Out of memory\");\n"
        "    return ESP_ERR_NO_MEM;\n"
        "}\n"
        "ESP_ERROR_CHECK(gpio_pullup_en(GPIO_NUM_21));\n"
        "ESP_ERROR_CHECK(gpio_pullup_en(GPIO_NUM_22));"
    ),
    risks_limitations="Internal weak pull-ups (~45kΩ) may not support fast I2C speeds (>100kHz).",
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="esp32_technical_reference.pdf",
            page_number=45,
            relevant_snippet="GPIO21 and GPIO22 require external pull-up resistors for reliable I2C operation.",
            relevance_explanation="Explains physical bus requirement on ESP32 open-drain GPIOs.",
        )
    ],
    grounded_summary="ESP32 open-drain I2C lines must have pull-up resistors to 3.3V.",
    code_issues=[
        CodeIssue(
            kind="null_pointer",
            severity="critical",
            confirmed=True,
            description="malloc() return value used without NULL check.",
            location="main.c:18",
            evidence="uint8_t *buf = malloc(256); buf[0] = 0;",
            suggestion="if (!buf) return ESP_ERR_NO_MEM;",
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
            message="unused variable 'err'",
            code_context="esp_err_t err = i2c_driver_install(...);",
            likely_cause="Return code variable assigned but not validated.",
            suggested_fix="ESP_ERROR_CHECK(err);",
        )
    ],
    serial_log_events=[
        SerialLogEvent(
            event_type="panic",
            severity="critical",
            is_repeated=False,
            timestamp=None,
            message="Guru Meditation Error: Core 0 panic'ed (LoadProhibited)",
            evidence="Guru Meditation Error: Core 0 panic'ed (LoadProhibited) at PC 0x400d1234",
            likely_cause="Dereference of NULL pointer (0x00000000).",
            suggested_action="Fix unchecked malloc in main.c:18.",
        )
    ],
)


# ─────────────────────────────────────────────
# 1. Complete structured response with all fields
# ─────────────────────────────────────────────


class TestCompleteStructuredResponse:
    def test_full_response_serialization_and_deserialization(self) -> None:
        json_data = COMPLETE_DEBUG_RESPONSE.model_dump_json()
        restored = DebugResponse.model_validate_json(json_data)

        assert restored.problem_observed == COMPLETE_DEBUG_RESPONSE.problem_observed
        assert restored.root_cause_summary == COMPLETE_DEBUG_RESPONSE.root_cause_summary
        assert restored.confidence_level == "high"
        assert len(restored.evidence_used) == 4
        assert len(restored.likely_causes) == 2
        assert len(restored.recommended_steps) == 4
        assert restored.proposed_fix is not None
        assert restored.corrected_code is not None
        assert restored.risks_limitations is not None
        assert restored.follow_up_required is None


# ─────────────────────────────────────────────
# 2. All analysis fields coexisting simultaneously
# ─────────────────────────────────────────────


class TestAnalysisFieldsCoexistence:
    def test_code_issues_compiler_messages_serial_events_citations_coexist(self) -> None:
        res = COMPLETE_DEBUG_RESPONSE

        # Phase 4.1 field
        assert res.code_issues is not None
        assert len(res.code_issues) == 1
        assert res.code_issues[0].kind == "null_pointer"

        # Phase 4.2 field
        assert res.compiler_messages is not None
        assert len(res.compiler_messages) == 1
        assert res.compiler_messages[0].message_type == "warning"

        # Phase 4.3 field
        assert res.serial_log_events is not None
        assert len(res.serial_log_events) == 1
        assert res.serial_log_events[0].event_type == "panic"

        # Phase 3.4 fields
        assert res.datasheet_citations is not None
        assert len(res.datasheet_citations) == 1
        assert res.grounded_summary is not None


# ─────────────────────────────────────────────
# 3. Missing / optional fields handled safely
# ─────────────────────────────────────────────


class TestMissingOptionalFields:
    def test_minimal_valid_debug_response(self) -> None:
        """Minimal DebugResponse with only required fields defaults optional fields to None."""
        minimal = DebugResponse(
            problem_observed="Firmware build failure.",
            evidence_used=["main.c:10: error: undefined reference"],
            likely_causes=[LikelyCause(cause="Missing source file", plausibility="high")],
            recommended_steps=["Add missing file to Makefile."],
            proposed_fix="Update build configuration.",
        )

        assert minimal.root_cause_summary is None
        assert minimal.confidence_level is None
        assert minimal.corrected_code is None
        assert minimal.risks_limitations is None
        assert minimal.follow_up_required is None
        assert minimal.datasheet_citations is None
        assert minimal.grounded_summary is None
        assert minimal.code_issues is None
        assert minimal.compiler_messages is None
        assert minimal.serial_log_events is None


# ─────────────────────────────────────────────
# 4. Confidence / evidence handling
# ─────────────────────────────────────────────


class TestConfidenceEvidenceHandling:
    def test_confidence_level_validation(self) -> None:
        for conf in ["high", "medium", "low"]:
            resp = DebugResponse(
                problem_observed="Issue",
                evidence_used=["Evidence"],
                likely_causes=[LikelyCause(cause="Cause", plausibility="medium")],
                recommended_steps=["Step"],
                proposed_fix="Fix",
                confidence_level=conf,  # type: ignore[arg-type]
            )
            assert resp.confidence_level == conf

    def test_invalid_confidence_level_raises_validation_error(self) -> None:
        with pytest.raises(Exception):
            DebugResponse(
                problem_observed="Issue",
                evidence_used=["Evidence"],
                likely_causes=[LikelyCause(cause="Cause", plausibility="medium")],
                recommended_steps=["Step"],
                proposed_fix="Fix",
                confidence_level="very_high",  # type: ignore[arg-type]
            )


# ─────────────────────────────────────────────
# 5. Grounded citations schema & traceability
# ─────────────────────────────────────────────


class TestGroundedCitationsTraceability:
    def test_citation_fields_preserved_accurately(self) -> None:
        citation = DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="stm32f4_reference_manual.pdf",
            page_number=128,
            relevant_snippet="TIM2 is a 32-bit general purpose timer located on APB1 bus.",
            relevance_explanation="Confirms timer resolution and bus clock domain.",
        )

        assert citation.document_name == "stm32f4_reference_manual.pdf"
        assert citation.page_number == 128
        assert "TIM2 is a 32-bit" in citation.relevant_snippet
        assert citation.relevance_explanation is not None


# ─────────────────────────────────────────────
# 6. Malformed and empty AI response handling
# ─────────────────────────────────────────────


class TestMalformedAndEmptyAiResponse:
    def test_empty_response_raises_value_error(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Empty Test"),
            firmware_code="void loop() {}",
        )
        mock_client = _fake_gemini_client("")
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="Empty response from Gemini API"):
                analyze_debugging_context(ctx)

    def test_malformed_json_raises_value_error(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Malformed Test"),
            firmware_code="void loop() {}",
        )
        mock_client = _fake_gemini_client("{not valid json")
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="Malformed response from Gemini API"):
                analyze_debugging_context(ctx)

    def test_schema_mismatch_raises_value_error(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Schema Test"),
            firmware_code="void loop() {}",
        )
        # Missing required problem_observed and likely_causes
        invalid_payload = json.dumps({"only_one_field": "test"})
        mock_client = _fake_gemini_client(invalid_payload)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="Malformed response from Gemini API"):
                analyze_debugging_context(ctx)


# ─────────────────────────────────────────────
# 7. Backward compatibility with older DebugResponse objects
# ─────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_payload_from_phase_1_or_2_deserializes_cleanly(self) -> None:
        legacy_dict = {
            "problem_observed": "Compiler error on line 42",
            "evidence_used": ["main.c:42: error: expected ';'"],
            "likely_causes": [{"cause": "Missing semicolon", "plausibility": "high"}],
            "recommended_steps": ["Add semicolon on line 41"],
            "proposed_fix": "Add semicolon",
            "corrected_code": "int a = 5;\n",
            "risks_limitations": None,
            "follow_up_required": None,
        }
        res = DebugResponse.model_validate(legacy_dict)
        assert res.problem_observed == "Compiler error on line 42"
        assert res.code_issues is None
        assert res.compiler_messages is None
        assert res.serial_log_events is None
        assert res.datasheet_citations is None


# ─────────────────────────────────────────────
# 8. Existing debug endpoint integration
# ─────────────────────────────────────────────


class TestDebugEndpointIntegration:
    def test_endpoint_returns_200_with_all_structured_fields(
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
            return_value=COMPLETE_DEBUG_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "firmware_code": "uint8_t *buf = malloc(256);",
                        "compiler_output": "main.c:35: warning: unused variable 'err'",
                        "serial_logs": "LoadProhibited panic",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["problem_observed"] == COMPLETE_DEBUG_RESPONSE.problem_observed
                assert data["root_cause_summary"] is not None
                assert data["confidence_level"] == "high"
                assert data["code_issues"] is not None
                assert data["compiler_messages"] is not None
                assert data["serial_log_events"] is not None
                assert data["datasheet_citations"] is not None
                assert data["grounded_summary"] is not None
            finally:
                app.dependency_overrides.clear()
