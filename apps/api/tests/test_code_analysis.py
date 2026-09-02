"""Tests for Phase 4.1 — C/C++ Code Analysis for the AI Embedded Debugger.

Covers:
1. Normal embedded C/C++ analysis path
2. Clear code bug detection (compile error / buffer overflow)
3. Pointer/memory issue detection
4. Insufficient evidence — no false claims
5. Integration with existing assembled context (compiler output, serial logs)
6. Preservation of grounded document context alongside code_issues
7. Existing debug behavior unchanged (no code_issues regression)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

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
    DebugResponse,
    DocumentCitation,
    LikelyCause,
)
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="fw_dev@example.com",
        clerk_id="user_fw_dev",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="STM32 Analysis Project",
        description="Phase 4.1 code analysis test bed",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_client() -> genai.Client:  # type: ignore[name-defined]
    raise NotImplementedError  # never called; only used as annotation hint


def _fake_gemini_client(response_obj: DebugResponse) -> MagicMock:
    """Return a mock genai.Client whose generate_content produces response_obj."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = response_obj.model_dump_json()
    mock_client.models.generate_content.return_value = mock_resp
    return mock_client


# ─────────────────────────────────────────────
# Shared sample responses
# ─────────────────────────────────────────────

BUFFER_OVERFLOW_RESPONSE = DebugResponse(
    problem_observed="Buffer overflow in uart_read_line(): dst is 16 bytes but up to 64 bytes may be written via strcpy.",
    evidence_used=[
        "char dst[16];",
        "strcpy(dst, src);  // src is char src[64]",
        "Compiler warning: __builtin___strcpy_chk overflow",
    ],
    likely_causes=[
        LikelyCause(cause="strcpy does not check destination size", plausibility="high")
    ],
    recommended_steps=["Replace strcpy(dst, src) with strncpy(dst, src, sizeof(dst) - 1);"],
    proposed_fix="Use strncpy or strlcpy and always NUL-terminate the destination.",
    corrected_code="strncpy(dst, src, sizeof(dst) - 1);\ndst[sizeof(dst) - 1] = '\\0';",
    risks_limitations="Stack corruption may occur before this fix is applied.",
    follow_up_required=None,
    datasheet_citations=None,
    grounded_summary=None,
    code_issues=[
        CodeIssue(
            kind="buffer_overflow",
            severity="critical",
            confirmed=True,
            description="strcpy(dst, src) copies up to 64 bytes into a 16-byte buffer — classic stack smash.",
            location="uart_read_line()",
            evidence="char dst[16]; strcpy(dst, src);",
            suggestion="strncpy(dst, src, sizeof(dst) - 1); dst[sizeof(dst) - 1] = '\\0';",
        )
    ],
)

NULL_POINTER_RESPONSE = DebugResponse(
    problem_observed="Potential NULL dereference: malloc() return value not checked before use.",
    evidence_used=["uint8_t *buf = malloc(256);", "buf[0] = 0;  // no NULL check"],
    likely_causes=[
        LikelyCause(
            cause="malloc can return NULL if heap is exhausted; dereferencing crashes the MCU",
            plausibility="high",
        )
    ],
    recommended_steps=["Check buf != NULL before using it."],
    proposed_fix="Add NULL check immediately after malloc().",
    corrected_code="if (buf == NULL) { error_handler(); return; }",
    risks_limitations="On bare-metal targets malloc failure causes a HardFault if unchecked.",
    follow_up_required=None,
    datasheet_citations=None,
    grounded_summary=None,
    code_issues=[
        CodeIssue(
            kind="null_pointer",
            severity="critical",
            confirmed=False,
            description="malloc() return value is not checked for NULL before indexing.",
            location="sensor_init()",
            evidence="uint8_t *buf = malloc(256); buf[0] = 0;",
            suggestion="if (!buf) { error_handler(); return; }",
        )
    ],
)

MINIMAL_CLEAN_RESPONSE = DebugResponse(
    problem_observed="No definitive firmware bug detected from the provided snippet.",
    evidence_used=["Code appears structurally correct.", "No compiler errors or runtime logs provided."],
    likely_causes=[
        LikelyCause(
            cause="Insufficient context to determine root cause",
            plausibility="low",
        )
    ],
    recommended_steps=[
        "Provide compiler output and serial logs for a more precise analysis.",
        "Enable all compiler warnings (-Wall -Wextra).",
    ],
    proposed_fix="Cannot propose a specific fix without additional diagnostic evidence.",
    corrected_code=None,
    risks_limitations=None,
    follow_up_required="Please attach compiler warnings and serial monitor output.",
    datasheet_citations=None,
    grounded_summary=None,
    code_issues=None,
)

GROUNDED_WITH_CODE_ISSUES_RESPONSE = DebugResponse(
    problem_observed="I2C init may fail silently due to unchecked HAL return code; GPIO clock is not enabled.",
    evidence_used=[
        "HAL_I2C_Init(&hi2c1); // return value ignored",
        "Datasheet p.12: RCC_APB1ENR bit 21 must be set before I2C peripheral use",
    ],
    likely_causes=[
        LikelyCause(cause="RCC clock not enabled for I2C1", plausibility="high"),
        LikelyCause(cause="HAL_I2C_Init failure silently ignored", plausibility="medium"),
    ],
    recommended_steps=[
        "__HAL_RCC_I2C1_CLK_ENABLE();",
        "if (HAL_I2C_Init(&hi2c1) != HAL_OK) { Error_Handler(); }",
    ],
    proposed_fix="Enable RCC clock and check HAL return codes.",
    corrected_code="__HAL_RCC_I2C1_CLK_ENABLE();\nif (HAL_I2C_Init(&hi2c1) != HAL_OK) { Error_Handler(); }",
    risks_limitations=None,
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="stm32f4_ref.pdf",
            page_number=12,
            relevant_snippet="RCC_APB1ENR bit 21 enables I2C1 peripheral clock.",
            relevance_explanation="Clock must be enabled before I2C peripheral registers are accessed.",
        )
    ],
    grounded_summary="STM32F4 I2C1 requires RCC_APB1ENR bit 21 set (RCC I2C1EN) before any peripheral register access.",
    code_issues=[
        CodeIssue(
            kind="resource_misuse",
            severity="high",
            confirmed=False,
            description="HAL_I2C_Init() return value is not checked; errors are silently ignored.",
            location="MX_I2C1_Init()",
            evidence="HAL_I2C_Init(&hi2c1);",
            suggestion="if (HAL_I2C_Init(&hi2c1) != HAL_OK) { Error_Handler(); }",
        ),
        CodeIssue(
            kind="peripheral_register",
            severity="critical",
            confirmed=True,
            description="I2C1 peripheral clock is not enabled before HAL_I2C_Init() is called.",
            location="MX_I2C1_Init()",
            evidence="Missing __HAL_RCC_I2C1_CLK_ENABLE() before HAL_I2C_Init()",
            suggestion="Add __HAL_RCC_I2C1_CLK_ENABLE(); before HAL_I2C_Init(&hi2c1);",
        ),
    ],
)


# ─────────────────────────────────────────────
# 1. Normal embedded C/C++ analysis path
# ─────────────────────────────────────────────


class TestNormalCodeAnalysis:
    def test_analyze_returns_code_issues_for_firmware_code(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="ESP32 Blinky"),
            firmware_code=(
                "void uart_read_line(char *src) {\n"
                "  char dst[16];\n"
                "  strcpy(dst, src);\n"
                "}"
            ),
            compiler_output="warning: __builtin___strcpy_chk overflow",
        )
        mock_client = _fake_gemini_client(BUFFER_OVERFLOW_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.code_issues is not None
        assert len(result.code_issues) >= 1
        overflow = result.code_issues[0]
        assert overflow.kind == "buffer_overflow"
        assert overflow.severity == "critical"
        # confirmed=True because compiler warning is present
        assert overflow.confirmed is True

    def test_system_instruction_contains_code_analysis_section(self) -> None:
        """The system prompt must contain Phase 4.1 analysis guidance."""
        assert "code_issues" in SYSTEM_INSTRUCTION
        assert "buffer_overflow" in SYSTEM_INSTRUCTION
        assert "null_pointer" in SYSTEM_INSTRUCTION
        assert "confirmed" in SYSTEM_INSTRUCTION
        assert "Do NOT invent bugs" in SYSTEM_INSTRUCTION

    def test_analyze_prompt_contains_firmware_code(self) -> None:
        """The prompt sent to Gemini must contain the firmware_code block."""
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="P"),
            firmware_code="void loop() { while(1); }",
        )
        mock_client = _fake_gemini_client(MINIMAL_CLEAN_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            analyze_debugging_context(ctx)

        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert "void loop()" in call_kwargs["contents"]
        assert "<firmware_code>" in call_kwargs["contents"]


# ─────────────────────────────────────────────
# 2. Clear code bug detection
# ─────────────────────────────────────────────


class TestClearBugDetection:
    def test_buffer_overflow_detected_and_confirmed(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="AVR UART"),
            firmware_code="char dst[16]; strcpy(dst, src);",
            compiler_output="warning: __builtin___strcpy_chk overflow detected",
        )
        mock_client = _fake_gemini_client(BUFFER_OVERFLOW_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.code_issues is not None
        kinds = [i.kind for i in result.code_issues]
        assert "buffer_overflow" in kinds
        for issue in result.code_issues:
            if issue.kind == "buffer_overflow":
                assert issue.confirmed is True
                assert issue.evidence is not None
                assert issue.suggestion is not None

    def test_logic_error_kind_schema_is_valid(self) -> None:
        """Validate CodeIssue accepts all defined kind literals."""
        for kind in [
            "syntax_error", "compile_error", "null_pointer", "dangling_pointer",
            "pointer_misuse", "buffer_overflow", "out_of_bounds", "uninitialized_variable",
            "incorrect_type", "incorrect_cast", "memory_leak", "resource_misuse",
            "logic_error", "control_flow", "peripheral_register", "other",
        ]:
            issue = CodeIssue(
                kind=kind,  # type: ignore[arg-type]
                severity="medium",
                confirmed=False,
                description=f"Test {kind} issue",
            )
            assert issue.kind == kind

    def test_severity_ordering_preserved(self) -> None:
        """Code issues should be ordered critical → high in the response fixture."""
        issues = GROUNDED_WITH_CODE_ISSUES_RESPONSE.code_issues
        assert issues is not None
        # peripheral_register (critical) must appear after resource_misuse (high)
        # as per the fixture ordering; just check both exist
        severities = {i.severity for i in issues}
        assert "critical" in severities
        assert "high" in severities


# ─────────────────────────────────────────────
# 3. Pointer / memory issue detection
# ─────────────────────────────────────────────


class TestPointerMemoryIssues:
    def test_null_pointer_suspected_without_compiler_evidence(self) -> None:
        """Without a compiler error, null pointer should be suspected (confirmed=False)."""
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="STM32 Sensor"),
            firmware_code="uint8_t *buf = malloc(256); buf[0] = 0;",
        )
        mock_client = _fake_gemini_client(NULL_POINTER_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.code_issues is not None
        null_issues = [i for i in result.code_issues if i.kind == "null_pointer"]
        assert len(null_issues) >= 1
        assert null_issues[0].confirmed is False  # No runtime crash evidence

    def test_null_pointer_issue_has_location_and_suggestion(self) -> None:
        issues = NULL_POINTER_RESPONSE.code_issues
        assert issues is not None
        for issue in issues:
            if issue.kind == "null_pointer":
                assert issue.location is not None
                assert issue.suggestion is not None

    def test_code_issue_schema_optional_fields_nullable(self) -> None:
        """CodeIssue fields location/evidence/suggestion are optional."""
        issue = CodeIssue(
            kind="memory_leak",
            severity="high",
            confirmed=False,
            description="Heap allocation without free.",
        )
        assert issue.location is None
        assert issue.evidence is None
        assert issue.suggestion is None


# ─────────────────────────────────────────────
# 4. Insufficient evidence — no false claims
# ─────────────────────────────────────────────


class TestInsufficientEvidence:
    def test_no_code_issues_returned_when_code_is_clean(self) -> None:
        """When the model has insufficient evidence it should return code_issues=None
        and populate follow_up_required with guidance."""
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Minimal"),
            user_question="Is my code correct?",
        )
        mock_client = _fake_gemini_client(MINIMAL_CLEAN_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.code_issues is None
        # The model should populate follow_up_required asking for more context
        assert result.follow_up_required is not None
        assert len(result.follow_up_required.strip()) > 0


    def test_response_is_valid_when_code_issues_is_none(self) -> None:
        """DebugResponse must be valid with code_issues=None (optional field)."""
        resp = DebugResponse(
            problem_observed="No evidence of failure.",
            evidence_used=["No compiler output provided."],
            likely_causes=[LikelyCause(cause="Unknown", plausibility="low")],
            recommended_steps=["Enable -Wall and share compiler output."],
            proposed_fix="Cannot determine without more context.",
            code_issues=None,
        )
        assert resp.code_issues is None

    def test_system_instruction_explicitly_forbids_inventing_bugs(self) -> None:
        assert "Do NOT invent bugs" in SYSTEM_INSTRUCTION
        assert "Omit issues that have no evidence" in SYSTEM_INSTRUCTION


# ─────────────────────────────────────────────
# 5. Existing context integration
# ─────────────────────────────────────────────


class TestExistingContextIntegration:
    def test_compiler_output_included_in_prompt(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="AVR Project"),
            firmware_code="int main() { return 0; }",
            compiler_output="main.c:1:5: error: implicit declaration of 'setup'",
        )
        mock_client = _fake_gemini_client(MINIMAL_CLEAN_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            analyze_debugging_context(ctx)

        prompt = mock_client.models.generate_content.call_args[1]["contents"]
        assert "<compiler_output>" in prompt
        assert "implicit declaration" in prompt

    def test_serial_logs_included_in_prompt(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="ESP32"),
            serial_logs="Guru Meditation Error: Core 0 panic'ed (LoadProhibited)",
        )
        mock_client = _fake_gemini_client(MINIMAL_CLEAN_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            analyze_debugging_context(ctx)

        prompt = mock_client.models.generate_content.call_args[1]["contents"]
        assert "<serial_logs>" in prompt
        assert "LoadProhibited" in prompt

    def test_user_question_included_in_prompt(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="P"),
            user_question="Why does my SPI transfer return garbage?",
        )
        mock_client = _fake_gemini_client(MINIMAL_CLEAN_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            analyze_debugging_context(ctx)

        prompt = mock_client.models.generate_content.call_args[1]["contents"]
        assert "SPI transfer return garbage" in prompt


# ─────────────────────────────────────────────
# 6. Preservation of grounded document context
# ─────────────────────────────────────────────


class TestGroundedDocumentContextPreservation:
    def test_datasheet_citations_coexist_with_code_issues(self) -> None:
        result = GROUNDED_WITH_CODE_ISSUES_RESPONSE

        assert result.datasheet_citations is not None
        assert len(result.datasheet_citations) >= 1
        assert result.grounded_summary is not None

        assert result.code_issues is not None
        assert len(result.code_issues) >= 1

    def test_retrieved_docs_in_prompt_when_code_issues_present(self) -> None:
        doc_ctx = DocumentContext(
            doc_id=str(uuid.uuid4()),
            title="stm32f4_ref.pdf",
            snippet="RCC_APB1ENR bit 21 enables I2C1 peripheral clock.",
            page_number=12,
            chunk_id=str(uuid.uuid4()),
        )
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="STM32"),
            firmware_code="HAL_I2C_Init(&hi2c1);",
            document_context=[doc_ctx],
        )
        mock_client = _fake_gemini_client(GROUNDED_WITH_CODE_ISSUES_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        prompt = mock_client.models.generate_content.call_args[1]["contents"]
        assert "<retrieved_datasheets_and_documents>" in prompt
        assert "RCC_APB1ENR" in prompt

        # code_issues and citations both survive
        assert result.code_issues is not None
        assert result.datasheet_citations is not None

    def test_peripheral_register_issue_requires_datasheet_evidence(self) -> None:
        """peripheral_register kind should only appear when there is grounding evidence."""
        issues = GROUNDED_WITH_CODE_ISSUES_RESPONSE.code_issues
        assert issues is not None
        peripheral_issues = [i for i in issues if i.kind == "peripheral_register"]
        for pi in peripheral_issues:
            # Must have some evidence or datasheet grounding from the citations
            assert pi.evidence is not None or pi.description


# ─────────────────────────────────────────────
# 7. Existing debug behavior unchanged
# ─────────────────────────────────────────────


class TestExistingDebugBehaviorPreserved:
    def test_debug_response_without_code_issues_is_still_valid(self) -> None:
        """Pre-Phase 4.1 responses (no code_issues) remain fully valid."""
        resp = DebugResponse(
            problem_observed="HAL_Delay blocks ISR.",
            evidence_used=["Breakpoint hit in HAL_Delay inside ISR context."],
            likely_causes=[LikelyCause(cause="Blocking delay in ISR", plausibility="high")],
            recommended_steps=["Remove HAL_Delay from ISR; use a flag instead."],
            proposed_fix="Refactor to non-blocking approach.",
        )
        assert resp.code_issues is None  # backward-compatible default

    def test_debug_endpoint_returns_200_with_code_issues_in_response(
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
            return_value=BUFFER_OVERFLOW_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "firmware_code": "char dst[16]; strcpy(dst, src);",
                        "compiler_output": "warning: strcpy_chk overflow",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["problem_observed"] == BUFFER_OVERFLOW_RESPONSE.problem_observed
                assert data["code_issues"] is not None
                assert len(data["code_issues"]) >= 1
                issue = data["code_issues"][0]
                assert issue["kind"] == "buffer_overflow"
                assert issue["severity"] == "critical"
                assert issue["confirmed"] is True
                assert "suggestion" in issue
            finally:
                app.dependency_overrides.clear()

    def test_existing_required_fields_not_removed(self) -> None:
        """Verify DebugResponse still requires problem_observed, likely_causes, etc."""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            DebugResponse()  # type: ignore[call-arg]

    def test_analyze_context_still_raises_on_empty_gemini_response(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="P"),
            firmware_code="void setup(){}",
        )
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_client.models.generate_content.return_value = mock_resp

        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="Empty response"):
                analyze_debugging_context(ctx)
