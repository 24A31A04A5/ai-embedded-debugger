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
    page_texts: list[str] = Field(default_factory=list)


class DocumentChunkResponse(BaseModel):
    """Schema for a single document chunk in API responses."""

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None = None
    metadata_json: dict[str, Any] | None = None
    embedding_model: str | None = None
    has_embedding: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RawChunk(BaseModel):
    """In-memory representation of a chunk before persistence."""

    chunk_index: int
    content: str
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSearchRequest(BaseModel):
    """Request payload for semantic vector search across project documents."""

    query: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of chunks to return")
    similarity_threshold: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity threshold (between -1.0 and 1.0)",
    )
    document_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Optional filter by specific document IDs within the project",
    )


class DocumentSearchResultItem(BaseModel):
    """Schema for an individual search result chunk with traceability metadata."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    page_number: int | None = None
    chunk_index: int
    similarity_score: float
    metadata_json: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentSearchResponse(BaseModel):
    """Response payload for document search."""

    query: str
    results: list[DocumentSearchResultItem]
    total_results: int
