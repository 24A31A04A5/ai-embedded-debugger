from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Sequence

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

if TYPE_CHECKING:
    from app.services.retrieval import DocumentRetrievalService

logger = logging.getLogger(__name__)

# Budget defaults (characters)
MAX_FILE_CHARS = 40_000
MAX_TEXT_INPUT_CHARS = 50_000
MAX_SESSION_HISTORY_MESSAGES = 10
MAX_SESSION_HISTORY_CHARS = 20_000
MAX_DOCUMENT_CHARS = 40_000
MAX_TOTAL_CONTEXT_CHARS = 200_000

# Patterns for embedded technical identifiers
_MCU_PERIPHERAL_RE = re.compile(
    r"\b(?:GPIO\w+|TIM\w+|USART\w+|UART\w+|I2C\w*|SPI\w*|DMA\w*|ADC\w*|DAC\w*|RCC\w*|NVIC\w*|"
    r"SysTick|EXTI\w*|FLASH\w*|PWR\w*|CRC\w*|WWDG|IWDG|"
    r"ESP32|STM32\w*|nRF\w+|PIC\w*|AVR\w*|Cortex-M\w*|ARM\w*|Xtensa\w*)\b",
    re.IGNORECASE,
)
_REGISTER_RE = re.compile(
    r"\b(?:0x[0-9A-Fa-f]{2,}|CR\d+|SR\d+|DR\d+|CTRL|CONFIG|STATUS|INT|IRQ|ISR|"
    r"register|bitfield|bit\s+\d+|R/W|reset\s+value|offset)\b",
    re.IGNORECASE,
)
_PIN_RE = re.compile(
    r"\b(?:GPIO\d+|Pin\s+\d+|PA\d+|PB\d+|PC\d+|PD\d+|PE\d+|"
    r"SDA|SCL|MOSI|MISO|SCK|TXD|RXD|PWM|ADC\d+|alternate\s+function)\b",
    re.IGNORECASE,
)
_SPEC_RE = re.compile(
    r"\b(?:voltage|current|VCC|VDD|VSS|GND|timing|frequency|baud|"
    r"MHz|kHz|Hz|mA|µA|nA|mV|µV|ms|µs|ns|min|max|typ|operating|"
    r"electrical|absolute\s+maximum)\b",
    re.IGNORECASE,
)


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


def _extract_technical_keywords(text: str) -> list[str]:
    """Extract embedded-domain keywords from text for retrieval query enrichment."""
    if not text:
        return []
    keywords: list[str] = []
    for pattern in (_MCU_PERIPHERAL_RE, _REGISTER_RE, _PIN_RE, _SPEC_RE):
        for m in pattern.finditer(text):
            kw = m.group(0).strip()
            if kw and kw not in keywords:
                keywords.append(kw)
    return keywords[:12]  # cap to avoid query bloat


def _build_technical_retrieval_query(
    user_question: str,
    compiler_output: str,
    firmware_code: str,
    base_query: str,
) -> str:
    """Build a semantically richer retrieval query for embedded documentation.

    Appends MCU/peripheral/register/pin/spec identifiers found in the supplied
    text so that retrieval surfaces register descriptions, pinout tables, and
    electrical specs ahead of generic prose chunks.

    Returns the enriched query (or the base_query unchanged if no keywords found).
    """
    combined = " ".join(
        [
            user_question[:500],
            compiler_output[:300],
            firmware_code[:500],
        ]
    )
    keywords = _extract_technical_keywords(combined)
    if not keywords:
        return base_query

    # Append unique keywords not already in base_query
    base_lower = base_query.lower()
    extras = [kw for kw in keywords if kw.lower() not in base_lower]
    if not extras:
        return base_query

    enriched = base_query.rstrip() + " " + " ".join(extras)
    return enriched[:2000]  # guard against excessively long queries


class ContextAssemblyService:
    """Assembles all sources of debugging evidence into a structured, bounded context model."""

    def __init__(
        self,
        db: Session,
        storage: BaseStorageService | None = None,
        max_file_chars: int = MAX_FILE_CHARS,
        max_text_chars: int = MAX_TEXT_INPUT_CHARS,
        max_session_history_messages: int = MAX_SESSION_HISTORY_MESSAGES,
        max_session_chars: int = MAX_SESSION_HISTORY_CHARS,
        max_doc_chars: int = MAX_DOCUMENT_CHARS,
        max_total_chars: int = MAX_TOTAL_CONTEXT_CHARS,
    ) -> None:
        self.db = db
        self.storage = storage
        self.max_file_chars = max_file_chars
        self.max_text_chars = max_text_chars
        self.max_session_history_messages = max_session_history_messages
        self.max_session_chars = max_session_chars
        self.max_doc_chars = max_doc_chars
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
        selected_document_ids: Sequence[uuid.UUID | str] | None = None,
        session_id: uuid.UUID | str | None = None,
        document_context: list[DocumentContext] | None = None,
        retrieval_service: DocumentRetrievalService | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
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

        # 6. Retrieved Document Context (Phase 3.3 / Phase 3.4)
        assembled_docs: list[DocumentContext] = []
        raw_docs = list(document_context) if document_context else []

        if not raw_docs and retrieval_service is not None:
            retrieval_query = ""
            if user_question and user_question.strip():
                retrieval_query = user_question.strip()
            elif compiler_output and compiler_output.strip():
                retrieval_query = "\n".join(compiler_output.strip().splitlines()[:5])
            elif serial_logs and serial_logs.strip():
                retrieval_query = "\n".join(serial_logs.strip().splitlines()[:5])
            elif firmware_code and firmware_code.strip():
                retrieval_query = "\n".join(firmware_code.strip().splitlines()[:5])

            if retrieval_query:
                # Phase 5.3: Compose a richer technical query by appending peripheral/register
                # keywords found in the user question and compiler output. This surfaces
                # register, pinout and specification chunks over generic text.
                enriched_query = _build_technical_retrieval_query(
                    user_question=user_question or "",
                    compiler_output=compiler_output or "",
                    firmware_code=firmware_code or "",
                    base_query=retrieval_query,
                )
                try:
                    valid_doc_uuids = None
                    if selected_document_ids:
                        valid_doc_uuids = [
                            uuid.UUID(str(did)) for did in selected_document_ids
                        ]

                    retrieved_results = retrieval_service.search(
                        project_id=project.id,
                        query=enriched_query,
                        top_k=top_k,
                        similarity_threshold=similarity_threshold,
                        document_ids=valid_doc_uuids,
                    )
                    raw_docs = [
                        DocumentContext(
                            doc_id=str(item.document_id),
                            title=item.document_name,
                            snippet=item.content,
                            source=item.document_name,
                            score=item.similarity_score,
                            chunk_id=str(item.chunk_id),
                            page_number=item.page_number,
                            chunk_index=item.chunk_index,
                            # Phase 5.3 — embedded source traceability
                            content_type=(item.metadata_json or {}).get("content_type"),
                            section=(item.metadata_json or {}).get("section"),
                            metadata_json=item.metadata_json,
                        )
                        for item in retrieved_results
                    ]
                except Exception as e:
                    logger.warning("Vector retrieval during context assembly failed: %s", e)
                    raw_docs = []

        total_doc_chars = 0
        for doc in raw_docs:
            snippet_text = doc.snippet
            if total_doc_chars + len(snippet_text) > self.max_doc_chars:
                remaining_budget = max(0, self.max_doc_chars - total_doc_chars)
                snippet_text, d_trunc, _, _, _ = truncate_text(
                    snippet_text, remaining_budget, f"Document '{doc.title or doc.doc_id}'"
                )
                is_any_truncated = True
                truncation_notes.append("Retrieved datasheet context truncated to character budget")
                doc = doc.model_copy(update={"snippet": snippet_text})

            total_doc_chars += len(snippet_text)
            assembled_docs.append(doc)
            if total_doc_chars >= self.max_doc_chars:
                break

        return AssembledDebugContext(
            project=project_ctx,
            user_question=user_question,
            firmware_code=fw_code,
            compiler_output=comp_out,
            serial_logs=ser_logs,
            uploaded_files=assembled_files,
            session_history=session_history_items,
            document_context=assembled_docs,
            is_truncated=is_any_truncated,
            truncation_notes=truncation_notes,
        )

