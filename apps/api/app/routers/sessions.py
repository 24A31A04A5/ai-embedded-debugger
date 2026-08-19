from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.gemini import analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.debug_message import DebugMessage
from app.models.debug_session import DebugSession
from app.models.project import Project
from app.models.user import User
from app.schemas.debug import DebugResponse
from app.schemas.session import (
    DebugSessionCreate,
    DebugSessionDetail,
    DebugSessionSummary,
)
from app.services.context_assembly import ContextAssemblyService
from app.services.storage import BaseStorageService, get_storage_service

router = APIRouter(prefix="/projects", tags=["sessions"])


def _get_project_for_user(
    project_id: str,
    current_user: User,
    db: Session,
) -> Project:
    """Verify that a project exists and is owned by the current user."""
    try:
        proj_uuid = uuid.UUID(project_id)
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
    "/{project_id}/sessions",
    response_model=DebugSessionDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_debug_session(
    project_id: str,
    request: DebugSessionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> DebugSessionDetail:
    """Create a new debug session: run AI analysis and persist both the request and the response."""
    project = _get_project_for_user(project_id, current_user, db)

    # Assemble context
    context_service = ContextAssemblyService(db=db, storage=storage)
    assembled_context = context_service.assemble_context(
        project_id=project_id,
        current_user=current_user,
        firmware_code=request.firmware_code,
        compiler_output=request.compiler_output,
        serial_logs=request.serial_logs,
        user_question=request.user_question,
        selected_file_ids=request.selected_file_ids,
    )

    # Auto-generate a title from the user question or firmware code if not explicitly given
    title = request.title
    if title == "Untitled Session":
        if request.user_question and request.user_question.strip():
            title = request.user_question.strip()[:80]
        elif request.firmware_code.strip():
            first_line = request.firmware_code.strip().split("\n")[0][:80]
            title = first_line if first_line else "Debug Session"

    # Call the AI with assembled context
    try:
        diagnosis: DebugResponse = analyze_debugging_context(assembled_context)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Analysis failed: {e}",
        ) from e

    # Create the session
    session_id = uuid.uuid4()
    db_session = DebugSession(
        id=session_id,
        project_id=project.id,
        user_id=current_user.id,
        title=title,
    )
    db.add(db_session)

    # Build user message content — compact representation of the submitted context
    user_content_parts: list[str] = []
    if request.user_question and request.user_question.strip():
        user_content_parts.append(f"[user_question]\n{request.user_question.strip()}")
    if request.firmware_code.strip():
        user_content_parts.append(f"[firmware_code]\n{request.firmware_code}")
    if request.compiler_output.strip():
        user_content_parts.append(f"[compiler_output]\n{request.compiler_output}")
    if request.serial_logs.strip():
        user_content_parts.append(f"[serial_logs]\n{request.serial_logs}")
    if assembled_context.uploaded_files:
        files_summary = ", ".join(f.filename for f in assembled_context.uploaded_files)
        user_content_parts.append(f"[files_included]\n{files_summary}")
    user_content = "\n\n".join(user_content_parts)

    user_msg = DebugMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="user",
        content=user_content,
    )
    db.add(user_msg)

    # Build assistant message — store the structured diagnosis as JSON
    assistant_content = diagnosis.model_dump_json()
    assistant_msg = DebugMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="assistant",
        content=assistant_content,
    )
    db.add(assistant_msg)

    db.commit()
    db.refresh(db_session)

    return DebugSessionDetail.model_validate(db_session)


@router.get(
    "/{project_id}/sessions",
    response_model=list[DebugSessionSummary],
)
def list_debug_sessions(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DebugSessionSummary]:
    """List all debug sessions for a project, newest first."""
    project = _get_project_for_user(project_id, current_user, db)

    sessions = (
        db.query(DebugSession)
        .filter(
            DebugSession.project_id == project.id,
            DebugSession.user_id == current_user.id,
        )
        .order_by(DebugSession.created_at.desc())
        .all()
    )

    return [DebugSessionSummary.model_validate(s) for s in sessions]


@router.get(
    "/{project_id}/sessions/{session_id}",
    response_model=DebugSessionDetail,
)
def get_debug_session(
    project_id: str,
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DebugSessionDetail:
    """Get a single debug session with all messages."""
    project = _get_project_for_user(project_id, current_user, db)

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from err

    db_session = (
        db.query(DebugSession)
        .filter(
            DebugSession.id == session_uuid,
            DebugSession.project_id == project.id,
            DebugSession.user_id == current_user.id,
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return DebugSessionDetail.model_validate(db_session)


@router.delete(
    "/{project_id}/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_debug_session(
    project_id: str,
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a debug session and all its messages."""
    project = _get_project_for_user(project_id, current_user, db)

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from err

    db_session = (
        db.query(DebugSession)
        .filter(
            DebugSession.id == session_uuid,
            DebugSession.project_id == project.id,
            DebugSession.user_id == current_user.id,
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    db.delete(db_session)
    db.commit()
