from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.gemini import analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rate_limiter import check_ai_rate_limit
from app.models.user import User
from app.schemas.debug import DebugRequest, DebugResponse
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

    import time
    from app.schemas.analytics import AnalyticsEventType
    from app.services.analytics import AnalyticsService

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
        import logging

        from app.core.security import sanitize_error_detail, sanitize_secrets

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

        logging.getLogger(__name__).error("AI Analysis failed: %s", sanitize_secrets(str(e)))
        error_msg = sanitize_error_detail(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Analysis failed: {error_msg}",
        ) from e


