from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.gemini import analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.debug import DebugRequest, DebugResponse
from app.services.context_assembly import ContextAssemblyService
from app.services.retrieval import DocumentRetrievalService
from app.services.storage import BaseStorageService, get_storage_service

router = APIRouter(prefix="/projects", tags=["debug"])


@router.post("/{project_id}/debug", response_model=DebugResponse)
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

    try:
        diagnosis = analyze_debugging_context(assembled_context)
        return diagnosis
    except Exception as e:
        import logging

        logging.getLogger(__name__).error("AI Analysis failed: %s", e)
        # Avoid leaking internal secrets / API keys in the response
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "key" in error_msg.lower():
            error_msg = "Gemini API connection or authentication failed."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Analysis failed: {error_msg}",
        ) from e

