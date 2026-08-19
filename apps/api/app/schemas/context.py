from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectContext(BaseModel):
    """Project-level metadata included in context."""

    project_id: UUID
    project_name: str
    description: str | None = None


class SessionHistoryItem(BaseModel):
    """Prior session interaction summary/snippet for context."""

    session_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = None


class UploadedFileContext(BaseModel):
    """Metadata and content for an uploaded project file included in context."""

    file_id: UUID
    filename: str
    file_type: Literal["code", "log"]
    size_bytes: int
    content: str
    is_truncated: bool = False
    original_length: int = 0
    truncated_length: int = 0


class DocumentContext(BaseModel):
    """Placeholder model for future RAG document context (Phase 3)."""

    doc_id: str | None = None
    title: str | None = None
    snippet: str
    source: str | None = None
    score: float | None = None


class AssembledDebugContext(BaseModel):
    """Complete, structured context assembled for the AI debugging pipeline."""

    project: ProjectContext
    user_question: str | None = None
    firmware_code: str = ""
    compiler_output: str = ""
    serial_logs: str = ""
    uploaded_files: list[UploadedFileContext] = Field(default_factory=list)
    session_history: list[SessionHistoryItem] = Field(default_factory=list)
    document_context: list[DocumentContext] = Field(default_factory=list)
    is_truncated: bool = False
    truncation_notes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")

    def format_prompt(self) -> str:
        """Render the assembled context into a clean, modular prompt string."""
        sections: list[str] = []

        # Project metadata
        proj_info = f"Project: {self.project.project_name} (ID: {self.project.project_id})"
        if self.project.description:
            proj_info += f"\nDescription: {self.project.description}"
        sections.append(f"<project_context>\n{proj_info}\n</project_context>")

        # User question / prompt
        if self.user_question and self.user_question.strip():
            sections.append(f"<user_question>\n{self.user_question.strip()}\n</user_question>")

        # Firmware source code
        if self.firmware_code.strip():
            sections.append(f"<firmware_code>\n{self.firmware_code.strip()}\n</firmware_code>")

        # Compiler output
        if self.compiler_output.strip():
            sections.append(f"<compiler_output>\n{self.compiler_output.strip()}\n</compiler_output>")

        # Serial / runtime logs
        if self.serial_logs.strip():
            sections.append(f"<serial_logs>\n{self.serial_logs.strip()}\n</serial_logs>")

        # Uploaded project files
        if self.uploaded_files:
            file_blocks: list[str] = []
            for f in self.uploaded_files:
                trunc_note = f" [TRUNCATED from {f.original_length} chars]" if f.is_truncated else ""
                file_blocks.append(
                    f'<file id="{f.file_id}" name="{f.filename}" type="{f.file_type}"{trunc_note}>\n{f.content}\n</file>'
                )
            sections.append("<uploaded_files>\n" + "\n".join(file_blocks) + "\n</uploaded_files>")

        # Session history (prior conversation context)
        if self.session_history:
            history_blocks: list[str] = []
            for item in self.session_history:
                history_blocks.append(f"[{item.role.upper()}]: {item.content}")
            sections.append("<session_history>\n" + "\n\n".join(history_blocks) + "\n</session_history>")

        # Future RAG document context placeholder
        if self.document_context:
            doc_blocks: list[str] = []
            for doc in self.document_context:
                source_attr = f' source="{doc.source}"' if doc.source else ""
                title_attr = f' title="{doc.title}"' if doc.title else ""
                doc_blocks.append(f"<document{title_attr}{source_attr}>\n{doc.snippet}\n</document>")
            sections.append("<indexed_documents>\n" + "\n".join(doc_blocks) + "\n</indexed_documents>")

        # Truncation notices
        if self.is_truncated and self.truncation_notes:
            notes_str = "\n".join(f"- {note}" for note in self.truncation_notes)
            sections.append(f"<context_limits_notice>\nWarning: Some context items were truncated to fit budget:\n{notes_str}\n</context_limits_notice>")

        return "\n\n".join(sections)
