from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsEventType(str, Enum):
    """Standardized event types for product and adoption metrics."""

    DEBUG_REQUEST_STARTED = "debug_request_started"
    DEBUG_REQUEST_COMPLETED = "debug_request_completed"
    DEBUG_REQUEST_FAILED = "debug_request_failed"
    FILE_UPLOADED = "file_uploaded"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_PROCESSING_FAILED = "document_processing_failed"
    SESSION_CREATED = "session_created"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    RETRIEVAL_PERFORMED = "retrieval_performed"


class AnalyticsEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    user_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    success: bool
    latency_ms: int | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime


class ProjectAnalyticsSummary(BaseModel):
    """Aggregated product metrics for a specific project workspace."""

    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    time_window_days: int = Field(default=30, description="Reporting window in days.")
    total_debug_requests: int = Field(default=0, description="Total debug analysis invocations.")
    successful_debug_requests: int = Field(default=0, description="Successful debug invocations.")
    failed_debug_requests: int = Field(default=0, description="Failed debug invocations.")
    avg_debug_latency_ms: float | None = Field(default=None, description="Average debug latency in ms.")
    total_files_uploaded: int = Field(default=0, description="Firmware and log files uploaded.")
    total_documents_uploaded: int = Field(default=0, description="Datasheets and manuals uploaded.")
    total_sessions_created: int = Field(default=0, description="Interactive debug sessions created.")
    feedback_count: int = Field(default=0, description="Total feedback submissions.")
    positive_feedback_count: int = Field(default=0, description="Positive rating submissions.")
    event_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Event breakdown counts keyed by event_type.",
    )
