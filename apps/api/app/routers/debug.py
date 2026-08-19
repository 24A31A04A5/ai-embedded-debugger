from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.gemini import analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.debug import DebugRequest, DebugResponse
from app.services.context_assembly import ContextAssemblyService
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
    assembled_context = context_service.assemble_context(
        project_id=project_id,
        current_user=current_user,
        firmware_code=request.firmware_code,
        compiler_output=request.compiler_output,
        serial_logs=request.serial_logs,
        user_question=request.user_question,
        selected_file_ids=request.selected_file_ids,
        session_id=request.session_id,
    )

    try:
        diagnosis = analyze_debugging_context(assembled_context)
        return diagnosis
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Analysis failed: {str(e)}",
        ) from e

