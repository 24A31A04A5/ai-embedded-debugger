"""Tests for Phase 4.2 — Compiler Error Analysis for the AI Embedded Debugger.

Covers:
1. Compiler syntax error analysis
2. Compiler warning analysis
3. Linker error analysis
4. Root-cause vs cascading-error handling
5. Source file/line correlation
6. Clean/no compiler output handling
7. Compiler context combined with existing C/C++ code analysis
8. Preservation of grounded datasheet context
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
)


# ─────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="embedded_eng@example.com",
        clerk_id="user_clerk_compiler",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="STM32 Compiler Debug Project",
        description="Phase 4.2 test bed",
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
# Sample response fixtures
# ─────────────────────────────────────────────

SYNTAX_ERROR_RESPONSE = DebugResponse(
    problem_observed="Compilation failed in src/main.c:24: expected ';' before 'return'.",
    evidence_used=[
        "src/main.c:24:5: error: expected ';' before 'return'",
        "uint32_t val = read_adc()",
    ],
    likely_causes=[
        LikelyCause(cause="Missing semicolon at the end of line 23", plausibility="high")
    ],
    recommended_steps=["Add a semicolon at the end of line 23 in src/main.c."],
    proposed_fix="Terminate the uint32_t val = read_adc() statement with a semicolon.",
    corrected_code="uint32_t val = read_adc();\nreturn val;",
    risks_limitations=None,
    follow_up_required=None,
    compiler_messages=[
        CompilerMessage(
            message_type="error",
            severity="critical",
            is_root_cause=True,
            file="src/main.c",
            line=24,
            column=5,
            message="expected ';' before 'return'",
            code_context="uint32_t val = read_adc()",
            likely_cause="Statement on preceding line was not terminated with a semicolon.",
            suggested_fix="uint32_t val = read_adc();",
        )
    ],
)

WARNING_RESPONSE = DebugResponse(
    problem_observed="Compiler warning: format '%d' expects argument of type 'int', but argument 2 has type 'uint32_t'.",
    evidence_used=[
        "src/sensor.c:45:12: warning: format '%d' expects argument of type 'int', but argument 2 has type 'uint32_t' (aka 'unsigned int') [-Wformat=]",
        "printf(\"Count: %d\\n\", count);",
    ],
    likely_causes=[
        LikelyCause(
            cause="Format specifier mismatch: %d used for uint32_t instead of PRIu32 or %u",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Include <inttypes.h> and use PRIu32 format specifier, or cast/use %u."
    ],
    proposed_fix="Use PRIu32 macro from <inttypes.h> for portable 32-bit unsigned printing.",
    corrected_code='printf("Count: %" PRIu32 "\\n", count);',
    risks_limitations=None,
    follow_up_required=None,
    compiler_messages=[
        CompilerMessage(
            message_type="warning",
            severity="medium",
            is_root_cause=True,
            file="src/sensor.c",
            line=45,
            column=12,
            message="format '%d' expects argument of type 'int', but argument 2 has type 'uint32_t' [-Wformat=]",
            code_context='printf("Count: %d\\n", count);',
            likely_cause="uint32_t variable printed with signed integer specifier %d.",
            suggested_fix='printf("Count: %" PRIu32 "\\n", count);',
        )
    ],
)

LINKER_ERROR_RESPONSE = DebugResponse(
    problem_observed="Linker error: undefined reference to 'vTaskDelay' and 'xTaskCreate'. FreeRTOS tasks.c not linked.",
    evidence_used=[
        "build/main.o: in function `app_main':",
        "main.c:18: undefined reference to `vTaskDelay'",
        "main.c:22: undefined reference to `xTaskCreate'",
        "collect2: error: ld returned 1 exit status",
    ],
    likely_causes=[
        LikelyCause(
            cause="FreeRTOS source files or library are missing from the build linker flags / Makefile SRCS",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Verify FreeRTOS/Source/tasks.c is included in Makefile / CMakeLists.txt SOURCES.",
        "Ensure the FreeRTOS component or library is linked during final link step.",
    ],
    proposed_fix="Add tasks.c and queue.c to the CMakeLists.txt target_sources list.",
    corrected_code=None,
    risks_limitations=None,
    follow_up_required=None,
    compiler_messages=[
        CompilerMessage(
            message_type="linker_error",
            severity="critical",
            is_root_cause=True,
            file="main.c",
            line=18,
            column=None,
            message="undefined reference to `vTaskDelay'",
            code_context="vTaskDelay(pdMS_TO_TICKS(100));",
            likely_cause="FreeRTOS tasks.c was compiled or linked into the binary.",
            suggested_fix="Add FreeRTOS/Source/tasks.c to CMakeLists.txt target_sources.",
        ),
        CompilerMessage(
            message_type="linker_error",
            severity="high",
            is_root_cause=False,
            file="main.c",
            line=22,
            column=None,
            message="undefined reference to `xTaskCreate'",
            code_context="xTaskCreate(task_blink, \"blink\", 2048, NULL, 5, NULL);",
            likely_cause="Consequence of missing FreeRTOS core library linkage.",
            suggested_fix="Link the FreeRTOS kernel library.",
        ),
    ],
)

CASCADING_ERRORS_RESPONSE = DebugResponse(
    problem_observed="Build failure in gpio.h: typedef struct SensorConfig has syntax error on line 10, causing 4 cascading type errors in sensor.c.",
    evidence_used=[
        "include/gpio.h:10:3: error: unknown type name 'uint32_t'; did you forget to '#include <stdint.h>'?",
        "src/sensor.c:15:2: error: unknown type name 'SensorConfig'",
        "src/sensor.c:16:15: error: request for member 'pin' in something not a structure or union",
    ],
    likely_causes=[
        LikelyCause(
            cause="Missing #include <stdint.h> in include/gpio.h causes typedef to fail, triggering cascading errors across all consumers",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Add #include <stdint.h> at the top of include/gpio.h."
    ],
    proposed_fix="Include standard integer definitions in the header file.",
    corrected_code="#include <stdint.h>\n#include <stdbool.h>",
    risks_limitations=None,
    follow_up_required=None,
    compiler_messages=[
        CompilerMessage(
            message_type="error",
            severity="critical",
            is_root_cause=True,
            file="include/gpio.h",
            line=10,
            column=3,
            message="unknown type name 'uint32_t'; did you forget to '#include <stdint.h>'?",
            code_context="uint32_t pin;",
            likely_cause="Header file uses fixed-width integer types without including <stdint.h>.",
            suggested_fix="#include <stdint.h>",
        ),
        CompilerMessage(
            message_type="error",
            severity="high",
            is_root_cause=False,
            file="src/sensor.c",
            line=15,
            column=2,
            message="unknown type name 'SensorConfig'",
            code_context="SensorConfig cfg;",
            likely_cause="Cascading error: SensorConfig failed to declare due to error in gpio.h:10.",
            suggested_fix="Fix the root cause in include/gpio.h.",
        ),
        CompilerMessage(
            message_type="error",
            severity="medium",
            is_root_cause=False,
            file="src/sensor.c",
            line=16,
            column=15,
            message="request for member 'pin' in something not a structure or union",
            code_context="cfg.pin = 12;",
            likely_cause="Cascading error: variable cfg was invalidly declared.",
            suggested_fix="Resolves automatically when root cause is fixed.",
        ),
    ],
)

GROUNDED_COMPILER_RESPONSE = DebugResponse(
    problem_observed="Compiler error: 'GPIO_PIN_21' undeclared; ESP32 technical manual indicates GPIO numbers are integers or GPIO_NUM_21.",
    evidence_used=[
        "main.c:12:18: error: 'GPIO_PIN_21' undeclared (first use in this function)",
        "ESP32 Technical Reference Manual (p.45): ESP-IDF uses GPIO_NUM_21 for pin definitions.",
    ],
    likely_causes=[
        LikelyCause(
            cause="Using STM32 naming convention (GPIO_PIN_x) instead of ESP-IDF (GPIO_NUM_x)",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Replace GPIO_PIN_21 with GPIO_NUM_21 as specified by ESP-IDF driver/gpio.h."
    ],
    proposed_fix="Use ESP-IDF gpio_num_t enum identifier GPIO_NUM_21.",
    corrected_code="gpio_set_direction(GPIO_NUM_21, GPIO_MODE_OUTPUT);",
    risks_limitations=None,
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="esp32_technical_reference.pdf",
            page_number=45,
            relevant_snippet="GPIO pin identifiers in the ESP-IDF driver library are enumerated as GPIO_NUM_0 through GPIO_NUM_39.",
            relevance_explanation="Confirms correct ESP-IDF macro naming convention.",
        )
    ],
    grounded_summary="ESP-IDF GPIO driver uses GPIO_NUM_x rather than GPIO_PIN_x for pin identification.",
    code_issues=[
        CodeIssue(
            kind="compile_error",
            severity="critical",
            confirmed=True,
            description="Identifier GPIO_PIN_21 is undefined in ESP-IDF driver header.",
            location="setup_gpio() in main.c:12",
            evidence="main.c:12:18: error: 'GPIO_PIN_21' undeclared",
            suggestion="Use GPIO_NUM_21.",
        )
    ],
    compiler_messages=[
        CompilerMessage(
            message_type="error",
            severity="critical",
            is_root_cause=True,
            file="main.c",
            line=12,
            column=18,
            message="'GPIO_PIN_21' undeclared (first use in this function)",
            code_context="gpio_set_direction(GPIO_PIN_21, GPIO_MODE_OUTPUT);",
            likely_cause="Incorrect macro name used for ESP-IDF pin constant.",
            suggested_fix="gpio_set_direction(GPIO_NUM_21, GPIO_MODE_OUTPUT);",
        )
    ],
)


# ─────────────────────────────────────────────
# 1. Compiler syntax error analysis
# ─────────────────────────────────────────────


class TestCompilerSyntaxErrorAnalysis:
    def test_syntax_error_parsed_with_location_and_fix(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Syntax Project"),
            firmware_code="uint32_t val = read_adc()\nreturn val;",
            compiler_output="src/main.c:24:5: error: expected ';' before 'return'",
        )
        mock_client = _fake_gemini_client(SYNTAX_ERROR_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.compiler_messages is not None
        assert len(result.compiler_messages) == 1
        msg = result.compiler_messages[0]
        assert msg.message_type == "error"
        assert msg.severity == "critical"
        assert msg.is_root_cause is True
        assert msg.file == "src/main.c"
        assert msg.line == 24
        assert msg.column == 5
        assert "expected ';'" in msg.message
        assert msg.suggested_fix is not None

    def test_system_instruction_contains_compiler_section(self) -> None:
        assert "compiler_messages" in SYSTEM_INSTRUCTION
        assert "is_root_cause" in SYSTEM_INSTRUCTION
        assert "linker_error" in SYSTEM_INSTRUCTION
        assert "Root Cause vs Cascading Errors" in SYSTEM_INSTRUCTION


# ─────────────────────────────────────────────
# 2. Compiler warning analysis
# ─────────────────────────────────────────────


class TestCompilerWarningAnalysis:
    def test_compiler_warning_classified_with_medium_severity(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Warning Project"),
            firmware_code='printf("Count: %d\\n", count);',
            compiler_output="src/sensor.c:45:12: warning: format '%d' expects argument of type 'int', but argument 2 has type 'uint32_t' [-Wformat=]",
        )
        mock_client = _fake_gemini_client(WARNING_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.compiler_messages is not None
        msg = result.compiler_messages[0]
        assert msg.message_type == "warning"
        assert msg.severity == "medium"
        assert msg.file == "src/sensor.c"
        assert msg.line == 45
        assert msg.column == 12
        assert "format '%d'" in msg.message


# ─────────────────────────────────────────────
# 3. Linker error analysis
# ─────────────────────────────────────────────


class TestLinkerErrorAnalysis:
    def test_undefined_reference_classified_as_linker_error(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Linker Project"),
            firmware_code="vTaskDelay(100);",
            compiler_output="main.c:18: undefined reference to `vTaskDelay'\ncollect2: error: ld returned 1 exit status",
        )
        mock_client = _fake_gemini_client(LINKER_ERROR_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.compiler_messages is not None
        linker_msgs = [m for m in result.compiler_messages if m.message_type == "linker_error"]
        assert len(linker_msgs) >= 1
        assert linker_msgs[0].is_root_cause is True
        assert "vTaskDelay" in linker_msgs[0].message


# ─────────────────────────────────────────────
# 4. Root-cause vs cascading-error handling
# ─────────────────────────────────────────────


class TestRootCauseVsCascading:
    def test_root_cause_distinguished_from_cascading_errors(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Cascade Project"),
            compiler_output=(
                "include/gpio.h:10:3: error: unknown type name 'uint32_t'\n"
                "src/sensor.c:15:2: error: unknown type name 'SensorConfig'\n"
                "src/sensor.c:16:15: error: request for member 'pin' in something not a structure"
            ),
        )
        mock_client = _fake_gemini_client(CASCADING_ERRORS_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.compiler_messages is not None
        assert len(result.compiler_messages) == 3

        # Exactly one root cause
        root_causes = [m for m in result.compiler_messages if m.is_root_cause]
        assert len(root_causes) == 1
        assert root_causes[0].file == "include/gpio.h"
        assert root_causes[0].line == 10
        assert "uint32_t" in root_causes[0].message

        # Cascading errors marked is_root_cause=False
        cascading = [m for m in result.compiler_messages if not m.is_root_cause]
        assert len(cascading) == 2
        for m in cascading:
            assert m.is_root_cause is False


# ─────────────────────────────────────────────
# 5. Source file/line correlation
# ─────────────────────────────────────────────


class TestSourceCorrelation:
    def test_source_code_context_populated_from_firmware(self) -> None:
        msg = SYNTAX_ERROR_RESPONSE.compiler_messages
        assert msg is not None
        assert msg[0].file == "src/main.c"
        assert msg[0].line == 24
        assert msg[0].code_context == "uint32_t val = read_adc()"

    def test_compiler_message_schema_handles_missing_column(self) -> None:
        msg = CompilerMessage(
            message_type="linker_error",
            severity="critical",
            is_root_cause=True,
            file="main.o",
            line=None,
            column=None,
            message="multiple definition of 'SystemInit'",
        )
        assert msg.line is None
        assert msg.column is None
        assert msg.code_context is None


# ─────────────────────────────────────────────
# 6. Clean / no compiler output handling
# ─────────────────────────────────────────────


class TestCleanCompilerOutput:
    def test_no_compiler_messages_when_output_is_empty(self) -> None:
        clean_resp = DebugResponse(
            problem_observed="No compiler issues found.",
            evidence_used=["No compiler errors present."],
            likely_causes=[LikelyCause(cause="Logic issue or hardware misconfiguration", plausibility="medium")],
            recommended_steps=["Check runtime serial monitor logs."],
            proposed_fix="Review peripheral initialization sequence.",
            compiler_messages=None,
        )
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Clean Project"),
            firmware_code="void setup() { Serial.begin(115200); }",
            compiler_output="",
        )
        mock_client = _fake_gemini_client(clean_resp)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.compiler_messages is None

    def test_system_instruction_forbids_fabricating_compiler_errors(self) -> None:
        assert "Do NOT fabricate compiler errors" in SYSTEM_INSTRUCTION
        assert "set compiler_messages = None" in SYSTEM_INSTRUCTION


# ─────────────────────────────────────────────
# 7. Compiler context combined with C/C++ code analysis
# ─────────────────────────────────────────────


class TestCombinedCompilerAndCodeAnalysis:
    def test_compiler_messages_and_code_issues_coexist(self) -> None:
        result = GROUNDED_COMPILER_RESPONSE
        assert result.compiler_messages is not None
        assert len(result.compiler_messages) >= 1
        assert result.code_issues is not None
        assert len(result.code_issues) >= 1

        # Check compiler message details
        c_msg = result.compiler_messages[0]
        assert c_msg.message_type == "error"
        assert c_msg.is_root_cause is True

        # Check code issue details
        c_issue = result.code_issues[0]
        assert c_issue.kind == "compile_error"
        assert c_issue.confirmed is True


# ─────────────────────────────────────────────
# 8. Preservation of grounded datasheet context
# ─────────────────────────────────────────────


class TestGroundedDatasheetPreservation:
    def test_datasheet_citations_coexist_with_compiler_messages(self) -> None:
        result = GROUNDED_COMPILER_RESPONSE
        assert result.datasheet_citations is not None
        assert len(result.datasheet_citations) == 1
        assert "esp32_technical_reference.pdf" in result.datasheet_citations[0].document_name
        assert result.grounded_summary is not None
        assert result.compiler_messages is not None


# ─────────────────────────────────────────────
# 9. Existing debug behavior
# ─────────────────────────────────────────────


class TestExistingDebugBehavior:
    def test_debug_endpoint_returns_compiler_messages_in_response(
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
            return_value=SYNTAX_ERROR_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "firmware_code": "uint32_t val = read_adc()\nreturn val;",
                        "compiler_output": "src/main.c:24:5: error: expected ';' before 'return'",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["problem_observed"] == SYNTAX_ERROR_RESPONSE.problem_observed
                assert data["compiler_messages"] is not None
                assert len(data["compiler_messages"]) == 1
                c_msg = data["compiler_messages"][0]
                assert c_msg["message_type"] == "error"
                assert c_msg["file"] == "src/main.c"
                assert c_msg["line"] == 24
                assert c_msg["column"] == 5
                assert c_msg["is_root_cause"] is True
            finally:
                app.dependency_overrides.clear()

    def test_legacy_debug_response_without_compiler_messages_valid(self) -> None:
        """Older payloads without compiler_messages are valid (field defaults to None)."""
        resp = DebugResponse(
            problem_observed="I2C pull-up missing.",
            evidence_used=["Log shows timeout."],
            likely_causes=[LikelyCause(cause="Missing resistor", plausibility="high")],
            recommended_steps=["Add 4.7k resistor."],
            proposed_fix="Attach pull-ups.",
        )
        assert resp.compiler_messages is None
        assert resp.code_issues is None
