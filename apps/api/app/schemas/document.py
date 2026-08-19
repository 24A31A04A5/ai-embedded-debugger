from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ExtractionStatus = Literal["pending", "processing", "ready", "failed"]


class DocumentBase(BaseModel):
    filename: str
    version: str | None = None
    size_bytes: int
    checksum: str
    extraction_status: ExtractionStatus
    page_count: int | None = None


class DocumentResponse(DocumentBase):
    """Document metadata response schema."""

    id: uuid.UUID
    project_id: uuid.UUID
    download_url: str | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    """Detailed document response including extracted text."""

    extracted_text: str | None = None
    text_length: int = 0


class DocumentExtractionResult(BaseModel):
    """Data transfer model for extracted text and metadata from a PDF file."""

    text: str
    page_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
