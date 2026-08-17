from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    """Schema for submitting feedback on a debug session."""

    rating: int = Field(..., ge=0, le=1, description="1 = helpful, 0 = not helpful")
    reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional explanation for the rating.",
    )


class FeedbackResponse(BaseModel):
    """Schema for returning feedback data."""

    id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID
    rating: int
    reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
