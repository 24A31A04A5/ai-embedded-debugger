import json
import time
import logging
from typing import Annotated, Optional

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.gemini import analyze_debugging_context, analyze_debugging_context_stream
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limiter import check_ai_rate_limit
from app.core.security import sanitize_error_detail, sanitize_secrets
from app.models.user import User
from app.schemas.analytics import AnalyticsEventType
from app.schemas.debug import DebugRequest, DebugResponse
from app.services.analytics import AnalyticsService
from app.services.context_assembly import ContextAssemblyService
from app.services.retrieval import DocumentRetrievalService
from app.services.storage import BaseStorageService, get_storage_service

router = APIRouter(prefix="/projects", tags=["debug"])


@router.post(
    "/{project_id}/debug",
    response_model=DebugResponse,
    dependencies=[Depends(check_ai_rate_limit)],
)
def analyze_project_debug_info(
    project_id: str,
    request: DebugRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> DebugResponse:
    """Assemble debugging context from files/inputs and analyze with AI."""
    context_service = ContextAssemblyService(db=db, storage=storage)
    retrieval_service = DocumentRetrievalService(db=db)

    assembled_context = context_service.assemble_context(
        project_id=project_id,
        current_user=current_user,
        firmware_code=request.firmware_code,
        compiler_output=request.compiler_output,
        serial_logs=request.serial_logs,
        user_question=request.user_question,
        selected_file_ids=request.selected_file_ids,
        selected_document_ids=request.selected_document_ids,
        session_id=request.session_id,
        retrieval_service=retrieval_service,
    )

    start_time = time.perf_counter()
    AnalyticsService.track_event(
        db,
        AnalyticsEventType.DEBUG_REQUEST_STARTED,
        user_id=current_user.id,
        project_id=project_id,
        session_id=request.session_id,
        metadata={
            "has_firmware_code": bool(request.firmware_code),
            "has_compiler_output": bool(request.compiler_output),
            "has_serial_logs": bool(request.serial_logs),
            "has_user_question": bool(request.user_question),
            "selected_files_count": len(request.selected_file_ids or []),
            "selected_docs_count": len(request.selected_document_ids or []),
        },
    )

    try:
        diagnosis = analyze_debugging_context(assembled_context)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        AnalyticsService.track_event(
            db,
            AnalyticsEventType.DEBUG_REQUEST_COMPLETED,
            user_id=current_user.id,
            project_id=project_id,
            session_id=request.session_id,
            success=True,
            latency_ms=latency_ms,
            metadata={
                "confidence_level": diagnosis.confidence_level,
                "code_issues_count": len(diagnosis.code_issues or []),
            },
        )
        return diagnosis
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        AnalyticsService.track_event(
            db,
            AnalyticsEventType.DEBUG_REQUEST_FAILED,
            user_id=current_user.id,
            project_id=project_id,
            session_id=request.session_id,
            success=False,
            latency_ms=latency_ms,
            metadata={"error_type": type(e).__name__},
        )

        logger = logging.getLogger(__name__)
        logger.error("AI Analysis failed: %s", sanitize_secrets(str(e)))
        error_msg = sanitize_error_detail(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Analysis failed: {error_msg}",
        ) from e


@router.post(
    "/{project_id}/debug/stream",
    dependencies=[Depends(check_ai_rate_limit)],
)
async def analyze_project_debug_info_stream(
    project_id: str,
    request: DebugRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Assemble debugging context and analyze with AI using streaming SSE.

    Features:
    - Timeout handling (30s default from settings)
    - Client disconnect detection
    - Heartbeat/keep-alive mechanism
    - Latency metrics tracking

    Note: Accepts DebugRequest as JSON body (Phase 11.1 - SSE streaming integration)
    """
    settings = get_settings()
    stream_timeout = settings.stream_timeout_seconds or 30
    heartbeat_interval = settings.stream_heartbeat_seconds or 15

    context_service = ContextAssemblyService(db=db, storage=storage)
    retrieval_service = DocumentRetrievalService(db=db)

    assembled_context = context_service.assemble_context(
        project_id=project_id,
        current_user=current_user,
        firmware_code=request.firmware_code,
        compiler_output=request.compiler_output,
        serial_logs=request.serial_logs,
        user_question=request.user_question,
        selected_file_ids=request.selected_file_ids,
        selected_document_ids=request.selected_document_ids,
        session_id=request.session_id,
        retrieval_service=retrieval_service,
    )

    start_time = time.perf_counter()
    chunks_sent = 0
    error_occurred = False
    error_message = ""

    async def event_generator():
        nonlocal chunks_sent, error_occurred, error_message
        last_heartbeat = time.perf_counter()

        try:
            # Stream AI chunks directly
            stream = analyze_debugging_context_stream(assembled_context)
            async for chunk in stream:
                # Check for timeout
                elapsed = time.perf_counter() - start_time
                if elapsed > stream_timeout:
                    yield "event: timeout\ndata: {\"error\": \"Stream timeout reached\", \"timeout_seconds\": " + str(stream_timeout) + "}\n\n"
                    break

                # Check heartbeat interval
                now = time.perf_counter()
                if now - last_heartbeat >= heartbeat_interval:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

                chunks_sent += 1
                # Wrap chunk in proper JSON structure with 'text' field
                yield f"data: {json.dumps({'text': chunk})}\n\n"

        except asyncio.CancelledError:
            error_message = "Stream cancelled"
            error_occurred = True
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        finally:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Track analytics event
            AnalyticsService.track_event(
                db,
                AnalyticsEventType.DEBUG_REQUEST_COMPLETED,
                user_id=current_user.id,
                project_id=project_id,
                session_id=request.session_id,
                success=not error_occurred,
                latency_ms=latency_ms,
                metadata={
                    "stream_mode": True,
                    "chunks_sent": chunks_sent,
                    "error_type": type(error_message).__name__ if error_occurred else None,
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
