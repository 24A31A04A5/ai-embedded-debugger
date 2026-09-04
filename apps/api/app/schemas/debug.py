from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field



class DebugRequest(BaseModel):
    firmware_code: str = Field(
        default="", max_length=200_000, description="The C/C++ firmware source code."
    )
    compiler_output: str = Field(
        default="", max_length=200_000, description="The compiler error output."
    )
    serial_logs: str = Field(
        default="", max_length=200_000, description="The serial monitor or runtime logs."
    )
    user_question: str | None = Field(
        default=None, max_length=10_000, description="Optional specific debugging question or prompt."
    )
    selected_file_ids: list[UUID] | None = Field(
        default=None, max_length=50, description="Optional list of uploaded project file IDs to include in context."
    )
    selected_document_ids: list[UUID] | None = Field(
        default=None, max_length=50, description="Optional list of uploaded project document IDs to scope retrieval."
    )
    session_id: UUID | None = Field(
        default=None, description="Optional session ID to incorporate prior session history."
    )



class LikelyCause(BaseModel):
    cause: str = Field(..., description="The potential root cause of the issue.")
    plausibility: Literal["high", "medium", "low"] = Field(
        ..., description="How likely this is to be the actual root cause."
    )


class CodeIssue(BaseModel):
    """A specific C/C++ code-level issue detected by static analysis reasoning."""

    kind: Literal[
        "syntax_error",
        "compile_error",
        "null_pointer",
        "dangling_pointer",
        "pointer_misuse",
        "buffer_overflow",
        "out_of_bounds",
        "uninitialized_variable",
        "incorrect_type",
        "incorrect_cast",
        "memory_leak",
        "resource_misuse",
        "logic_error",
        "control_flow",
        "peripheral_register",
        "other",
    ] = Field(..., description="Category of the detected code issue.")
    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        ..., description="Estimated severity of the issue."
    )
    confirmed: bool = Field(
        ...,
        description="True when there is direct evidence (compiler error, observable crash, etc.). False when suspected from static reasoning only.",
    )
    description: str = Field(..., description="Clear explanation of the issue.")
    location: str | None = Field(
        default=None,
        description="File name, function name, or line reference where the issue was identified, if determinable.",
    )
    evidence: str | None = Field(
        default=None,
        description="Specific code excerpt, error message, or log line that supports this finding.",
    )
    suggestion: str | None = Field(
        default=None,
        description="Recommended fix or next step for this specific issue.",
    )

class CompilerMessage(BaseModel):
    """A single parsed GCC/G++/linker diagnostic from the compiler output."""

    message_type: Literal["error", "warning", "note", "linker_error", "linker_warning", "other"] = Field(
        ..., description="Classification of the compiler/linker message."
    )
    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        ..., description="Impact level: critical/high for build-blocking errors, medium/low for warnings, info for notes."
    )
    is_root_cause: bool = Field(
        ...,
        description="True for the primary error that causes the build failure or is the underlying root cause. False for secondary/cascading errors triggered by the root cause.",
    )
    file: str | None = Field(
        default=None,
        description="Source file name or path reported by the compiler (e.g. 'main.c', 'src/uart.cpp').",
    )
    line: int | None = Field(
        default=None, description="Line number reported by the compiler, if present."
    )
    column: int | None = Field(
        default=None, description="Column number reported by the compiler, if present."
    )
    message: str = Field(..., description="The compiler/linker diagnostic message text.")
    code_context: str | None = Field(
        default=None,
        description="Relevant source code line or snippet at the reported location, if available in the provided source code.",
    )
    likely_cause: str | None = Field(
        default=None,
        description="Brief human-readable explanation of why this error/warning is occurring.",
    )
    suggested_fix: str | None = Field(
        default=None,
        description="Specific fix suggestion for this individual message.",
    )


class SerialLogEvent(BaseModel):
    """A classified runtime or serial log event extracted from serial/UART/system logs."""

    event_type: Literal[
        "runtime_error",
        "crash_fault",
        "panic",
        "watchdog_reset",
        "brownout_reset",
        "boot_failure",
        "timeout",
        "communication_error",
        "warning",
        "repeated_error",
        "unexpected_value",
        "timing_anomaly",
        "info",
        "other",
    ] = Field(..., description="Classification of the runtime/serial log event.")
    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        ..., description="Severity of this runtime event: critical/high for crashes/panics/timeouts, medium for warnings, info for normal events."
    )
    is_repeated: bool = Field(
        default=False,
        description="True if this error or warning appears multiple times consecutively or cyclically in the logs.",
    )
    repeat_count: int | None = Field(
        default=None,
        description="Estimated number of times this event was repeated in the log stream, if applicable.",
    )
    timestamp: str | None = Field(
        default=None,
        description="Timestamp or log index reported in the log (e.g. '[12.450s]', '14:23:01.102', or None).",
    )
    message: str = Field(..., description="The relevant log line or extracted message text.")
    evidence: str = Field(..., description="Exact snippet or excerpt from the serial logs.")
    likely_cause: str | None = Field(
        default=None,
        description="Underlying hardware, firmware, or protocol reason for this log event.",
    )
    suggested_action: str | None = Field(
        default=None,
        description="Recommended action, test, or check for this specific runtime event.",
    )


class DocumentCitation(BaseModel):
    chunk_id: UUID | str | None = Field(
        default=None, description="The chunk ID in the vector database."
    )
    document_id: UUID | str | None = Field(default=None, description="The document ID.")
    document_name: str = Field(..., description="The name or filename of the cited document.")
    page_number: int | None = Field(
        default=None, description="Page number where the cited information was found."
    )
    relevant_snippet: str | None = Field(
        default=None, description="Exact or summarized excerpt from the document."
    )
    relevance_explanation: str | None = Field(
        default=None, description="How this datasheet information relates to the diagnosed problem."
    )


class DebugResponse(BaseModel):
    problem_observed: str = Field(
        ..., description="A concise summary of the problem based on the evidence."
    )
    root_cause_summary: str | None = Field(
        default=None,
        description="Concise single-sentence summary of the primary root cause identified by the analysis.",
    )
    confidence_level: Literal["high", "medium", "low"] | None = Field(
        default=None,
        description="Overall confidence level in the diagnosis based on the completeness and directness of provided evidence.",
    )
    evidence_used: list[str] = Field(
        ..., description="Key pieces of evidence from the code or logs."
    )
    likely_causes: list[LikelyCause] = Field(..., description="Ranked list of likely causes.")
    recommended_steps: list[str] = Field(
        ..., description="Actionable verification or debugging steps in logical execution order."
    )
    proposed_fix: str = Field(..., description="Explanation of the proposed solution.")
    corrected_code: str | None = Field(
        default=None, description="The corrected code snippet or patch, if applicable."
    )
    risks_limitations: str | None = Field(
        default=None, description="Risks of the fix or hardware damage warnings."
    )
    follow_up_required: str | None = Field(
        default=None, description="What information is missing to make a confident diagnosis."
    )
    datasheet_citations: list[DocumentCitation] | None = Field(
        default=None,
        description="Traceable citations to retrieved datasheets/documents that grounded this diagnosis.",
    )
    grounded_summary: str | None = Field(
        default=None,
        description="Key technical facts or constraints derived directly from referenced datasheets/manuals.",
    )
    code_issues: list[CodeIssue] | None = Field(
        default=None,
        description=(
            "Structured list of detected C/C++ code issues. Each entry captures the issue kind, severity, "
            "whether it is confirmed by direct evidence or only suspected, a description, optional location, "
            "supporting evidence, and a fix suggestion."
        ),
    )
    compiler_messages: list[CompilerMessage] | None = Field(
        default=None,
        description=(
            "Structured list of parsed GCC/G++/linker diagnostics from the compiler output, identifying root cause vs cascading errors, source location, and individual fix suggestions."
        ),
    )
    serial_log_events: list[SerialLogEvent] | None = Field(
        default=None,
        description=(
            "Classified runtime log events, faults, panics, timeouts, or repeated anomalies extracted from serial logs."
        ),
    )



