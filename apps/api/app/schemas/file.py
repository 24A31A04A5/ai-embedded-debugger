from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectFileResponse(BaseModel):
    """Schema for file metadata responses."""

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_type: str
    size_bytes: int
    checksum: str
    created_at: datetime
    updated_at: datetime
    download_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectFileContentResponse(BaseModel):
    """Schema for file metadata plus text contents."""

    metadata: ProjectFileResponse
    content: str
