from __future__ import annotations

import logging
import uuid
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.debug_message import DebugMessage
from app.models.debug_session import DebugSession
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.schemas.context import (
    AssembledDebugContext,
    DocumentContext,
    ProjectContext,
    SessionHistoryItem,
    UploadedFileContext,
)
from app.services.storage import BaseStorageService

logger = logging.getLogger(__name__)

# Budget defaults (characters)
MAX_FILE_CHARS = 40_000
MAX_TEXT_INPUT_CHARS = 50_000
MAX_SESSION_HISTORY_MESSAGES = 10
MAX_SESSION_HISTORY_CHARS = 20_000
MAX_TOTAL_CONTEXT_CHARS = 200_000


def truncate_text(
    text: str, max_chars: int, label: str
) -> tuple[str, bool, int, int, str | None]:
    """Truncate text if it exceeds max_chars, returning truncation stats and note."""
    orig_len = len(text)
    if orig_len <= max_chars:
        return text, False, orig_len, orig_len, None

    truncated = text[:max_chars]
    note = f"{label} truncated from {orig_len} to {max_chars} characters"
    return truncated, True, orig_len, max_chars, note


class ContextAssemblyService:
    """Assembles all sources of debugging evidence into a structured, bounded context model."""

    def __init__(
        self,
        db: Session,
        storage: BaseStorageService,
        max_file_chars: int = MAX_FILE_CHARS,
        max_text_chars: int = MAX_TEXT_INPUT_CHARS,
        max_session_history_messages: int = MAX_SESSION_HISTORY_MESSAGES,
        max_session_chars: int = MAX_SESSION_HISTORY_CHARS,
        max_total_chars: int = MAX_TOTAL_CONTEXT_CHARS,
    ) -> None:
        self.db = db
        self.storage = storage
        self.max_file_chars = max_file_chars
        self.max_text_chars = max_text_chars
        self.max_session_history_messages = max_session_history_messages
        self.max_session_chars = max_session_chars
        self.max_total_chars = max_total_chars

    def assemble_context(
        self,
        project_id: uuid.UUID | str,
        current_user: User,
        firmware_code: str = "",
        compiler_output: str = "",
        serial_logs: str = "",
        user_question: str | None = None,
        selected_file_ids: Sequence[uuid.UUID | str] | None = None,
        session_id: uuid.UUID | str | None = None,
        document_context: list[DocumentContext] | None = None,
    ) -> AssembledDebugContext:
        """Assemble debugging context with project isolation, storage retrieval, and budget limits."""
        # 1. Verify project ownership
        try:
            proj_uuid = uuid.UUID(str(project_id))
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            ) from err

        project = (
            self.db.query(Project)
            .filter(Project.id == proj_uuid, Project.owner_id == current_user.id)
            .first()
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        truncation_notes: list[str] = []
        is_any_truncated = False

        # 2. Project metadata context
        project_ctx = ProjectContext(
            project_id=project.id,
            project_name=project.name,
            description=project.description,
        )

        # 3. User question & pasted text inputs (firmware, compiler output, serial logs)
        fw_code, fw_trunc, _, _, fw_note = truncate_text(
            firmware_code or "", self.max_text_chars, "Firmware code"
        )
        if fw_trunc and fw_note:
            is_any_truncated = True
            truncation_notes.append(fw_note)

        comp_out, comp_trunc, _, _, comp_note = truncate_text(
            compiler_output or "", self.max_text_chars, "Compiler output"
        )
        if comp_trunc and comp_note:
            is_any_truncated = True
            truncation_notes.append(comp_note)

        ser_logs, ser_trunc, _, _, ser_note = truncate_text(
            serial_logs or "", self.max_text_chars, "Serial logs"
        )
        if ser_trunc and ser_note:
            is_any_truncated = True
            truncation_notes.append(ser_note)

        # 4. Uploaded Project Files retrieval & truncation
        assembled_files: list[UploadedFileContext] = []
        if selected_file_ids:
            # Parse UUIDs safely
            valid_file_uuids: list[uuid.UUID] = []
            for fid in selected_file_ids:
                try:
                    valid_file_uuids.append(uuid.UUID(str(fid)))
                except ValueError as err:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Invalid file ID format: {fid}",
                    ) from err

            if valid_file_uuids:
                # Query files strictly bounded to this project
                db_files = (
                    self.db.query(ProjectFile)
                    .filter(
                        ProjectFile.project_id == project.id,
                        ProjectFile.id.in_(valid_file_uuids),
                    )
                    .all()
                )

                found_file_map = {f.id: f for f in db_files}

                # Maintain requested order and verify all exist
                for requested_id in valid_file_uuids:
                    if requested_id not in found_file_map:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Project file not found or unauthorized: {requested_id}",
                        )

                    db_file = found_file_map[requested_id]
                    try:
                        raw_bytes = self.storage.get_file(db_file.storage_key)
                    except FileNotFoundError as err:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"File content missing in storage for: {db_file.filename}",
                        ) from err

                    file_text = raw_bytes.decode("utf-8", errors="replace")
                    trunc_content, f_trunc, orig_l, trunc_l, f_note = truncate_text(
                        file_text, self.max_file_chars, f"File '{db_file.filename}'"
                    )
                    if f_trunc and f_note:
                        is_any_truncated = True
                        truncation_notes.append(f_note)

                    assembled_files.append(
                        UploadedFileContext(
                            file_id=db_file.id,
                            filename=db_file.filename,
                            file_type=db_file.file_type,  # type: ignore[arg-type]
                            size_bytes=db_file.size_bytes,
                            content=trunc_content,
                            is_truncated=f_trunc,
                            original_length=orig_l,
                            truncated_length=trunc_l,
                        )
                    )

        # 5. Session History retrieval (if session_id provided)
        session_history_items: list[SessionHistoryItem] = []
        if session_id:
            try:
                sess_uuid = uuid.UUID(str(session_id))
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found",
                ) from err

            # Verify session belongs to project and user
            db_session = (
                self.db.query(DebugSession)
                .filter(
                    DebugSession.id == sess_uuid,
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

            # Retrieve recent messages
            recent_messages = (
                self.db.query(DebugMessage)
                .filter(DebugMessage.session_id == db_session.id)
                .order_by(DebugMessage.created_at.desc())
                .limit(self.max_session_history_messages)
                .all()
            )
            # Re-order chronologically
            chronological_msgs = list(reversed(recent_messages))
            total_session_chars = 0

            for msg in chronological_msgs:
                msg_content = msg.content
                if total_session_chars + len(msg_content) > self.max_session_chars:
                    remaining_budget = max(0, self.max_session_chars - total_session_chars)
                    msg_content, _, _, _, _ = truncate_text(
                        msg_content, remaining_budget, f"Session message {msg.id}"
                    )
                    is_any_truncated = True
                    truncation_notes.append("Prior session history truncated to character budget")

                total_session_chars += len(msg_content)
                session_history_items.append(
                    SessionHistoryItem(
                        session_id=db_session.id,
                        role=msg.role,  # type: ignore[arg-type]
                        content=msg_content,
                        created_at=msg.created_at,
                    )
                )
                if total_session_chars >= self.max_session_chars:
                    break

        return AssembledDebugContext(
            project=project_ctx,
            user_question=user_question,
            firmware_code=fw_code,
            compiler_output=comp_out,
            serial_logs=ser_logs,
            uploaded_files=assembled_files,
            session_history=session_history_items,
            document_context=document_context or [],
            is_truncated=is_any_truncated,
            truncation_notes=truncation_notes,
        )
