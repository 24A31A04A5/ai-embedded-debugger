from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DebugMessageResponse(BaseModel):
    """Schema for a single message in a debug session."""

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    token_usage: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DebugSessionCreate(BaseModel):
    """Schema for creating a new debug session from a debug request."""

    title: str = Field(default="Untitled Session", max_length=255)
    firmware_code: str = Field(default="", description="The C/C++ firmware source code.")
    compiler_output: str = Field(default="", description="The compiler error output.")
    serial_logs: str = Field(default="", description="The serial monitor or runtime logs.")
    user_question: str | None = Field(
        default=None, description="Optional specific debugging question or prompt."
    )
    selected_file_ids: list[uuid.UUID] | None = Field(
        default=None, description="Optional list of uploaded project file IDs to include in context."
    )


class DebugSessionSummary(BaseModel):
    """Lightweight schema for listing sessions (no messages)."""

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DebugSessionDetail(BaseModel):
    """Full session including messages."""

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[DebugMessageResponse] = []

    model_config = ConfigDict(from_attributes=True)
