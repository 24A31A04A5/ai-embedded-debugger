from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DebugRequest(BaseModel):
    firmware_code: str = Field(default="", description="The C/C++ firmware source code.")
    compiler_output: str = Field(default="", description="The compiler error output.")
    serial_logs: str = Field(default="", description="The serial monitor or runtime logs.")
    user_question: str | None = Field(
        default=None, description="Optional specific debugging question or prompt."
    )
    selected_file_ids: list[UUID] | None = Field(
        default=None, description="Optional list of uploaded project file IDs to include in context."
    )
    selected_document_ids: list[UUID] | None = Field(
        default=None, description="Optional list of uploaded project document IDs to scope retrieval."
    )
    session_id: UUID | None = Field(
        default=None, description="Optional session ID to incorporate prior session history."
    )


class LikelyCause(BaseModel):
    cause: str = Field(..., description="The potential root cause of the issue.")
    plausibility: Literal["high", "medium", "low"] = Field(
        ..., description="How likely this is to be the actual root cause."
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
    evidence_used: list[str] = Field(
        ..., description="Key pieces of evidence from the code or logs."
    )
    likely_causes: list[LikelyCause] = Field(..., description="Ranked list of likely causes.")
    recommended_steps: list[str] = Field(
        ..., description="Actionable verification or debugging steps."
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
