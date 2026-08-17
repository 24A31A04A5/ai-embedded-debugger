from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.schemas.file import ProjectFileContentResponse, ProjectFileResponse
from app.services.storage import BaseStorageService, get_storage_service

router = APIRouter(prefix="/projects", tags=["files"])

CODE_EXTENSIONS = {".c", ".cpp", ".h", ".hpp", ".cc", ".cxx", ".ino"}
LOG_EXTENSIONS = {".log", ".txt"}
ALLOWED_EXTENSIONS = CODE_EXTENSIONS | LOG_EXTENSIONS


def get_project_for_user(
    project_id: uuid.UUID | str,
    current_user: User,
    db: Session,
) -> Project:
    """Verify that a project exists and is owned by the current authenticated user."""
    try:
        proj_uuid = uuid.UUID(str(project_id))
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from err

    project = (
        db.query(Project)
        .filter(Project.id == proj_uuid, Project.owner_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.post(
    "/{project_id}/files/upload",
    response_model=ProjectFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_file(
    project_id: str,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file_type: Annotated[str | None, Form()] = None,
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> ProjectFileResponse:
    """Upload a C/C++ firmware or log file to a project."""
    project = get_project_for_user(project_id, current_user, db)
    settings = get_settings()

    original_filename = file.filename or "uploaded_file"
    file_ext = Path(original_filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file extension '{file_ext}'. Allowed extensions: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Determine file type
    if not file_type:
        file_type = "code" if file_ext in CODE_EXTENSIONS else "log"
    elif file_type not in ("code", "log"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be either 'code' or 'log'",
        )

    # Read and check size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB",
        )

    # Checksum & storage
    checksum = hashlib.sha256(content).hexdigest()
    file_id = uuid.uuid4()
    safe_filename = Path(original_filename).name
    storage_key = f"projects/{project.id}/files/{file_id}_{safe_filename}"

    storage.upload_file(
        storage_key=storage_key,
        data=content,
        content_type=file.content_type or "application/octet-stream",
    )

    now = datetime.now(UTC)
    db_file = ProjectFile(
        id=file_id,
        project_id=project.id,
        filename=safe_filename,
        file_type=file_type,
        size_bytes=len(content),
        checksum=checksum,
        storage_key=storage_key,
        created_at=now,
        updated_at=now,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    download_url = storage.get_download_url(storage_key)
    res = ProjectFileResponse.model_validate(db_file)
    res.download_url = download_url
    return res


@router.get("/{project_id}/files", response_model=list[ProjectFileResponse])
def list_project_files(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> list[ProjectFileResponse]:
    """List all uploaded files for a project."""
    project = get_project_for_user(project_id, current_user, db)

    files = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project.id)
        .order_by(ProjectFile.created_at.desc())
        .all()
    )

    results: list[ProjectFileResponse] = []
    for f in files:
        res = ProjectFileResponse.model_validate(f)
        res.download_url = storage.get_download_url(f.storage_key)
        results.append(res)

    return results


@router.get("/{project_id}/files/{file_id}", response_model=ProjectFileContentResponse)
def get_project_file_content(
    project_id: str,
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> ProjectFileContentResponse:
    """Retrieve metadata and decoded text content for a specific file."""
    project = get_project_for_user(project_id, current_user, db)

    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from err

    db_file = (
        db.query(ProjectFile)
        .filter(ProjectFile.id == file_uuid, ProjectFile.project_id == project.id)
        .first()
    )
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    try:
        raw_bytes = storage.get_file(db_file.storage_key)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content not found in storage",
        ) from err

    text_content = raw_bytes.decode("utf-8", errors="replace")
    metadata_res = ProjectFileResponse.model_validate(db_file)
    metadata_res.download_url = storage.get_download_url(db_file.storage_key)

    return ProjectFileContentResponse(metadata=metadata_res, content=text_content)


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_file(
    project_id: str,
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> Response:
    """Delete a file from both object storage and the database."""
    project = get_project_for_user(project_id, current_user, db)

    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from err

    db_file = (
        db.query(ProjectFile)
        .filter(ProjectFile.id == file_uuid, ProjectFile.project_id == project.id)
        .first()
    )
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    storage.delete_file(db_file.storage_key)
    db.delete(db_file)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
