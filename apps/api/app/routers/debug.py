from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.gemini import analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.debug import DebugRequest, DebugResponse

router = APIRouter(prefix="/projects", tags=["debug"])


@router.post("/{project_id}/debug", response_model=DebugResponse)
def analyze_project_debug_info(
    project_id: str,
    request: DebugRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DebugResponse:
    """Analyze firmware and logs using AI and return a structured diagnosis."""
    # Verify the project exists and belongs to the user
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.owner_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        diagnosis = analyze_debugging_context(
            firmware_code=request.firmware_code,
            compiler_output=request.compiler_output,
            serial_logs=request.serial_logs,
        )
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
