from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.debug_session import DebugSession
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post(
    "/sessions/{session_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    session_id: str,
    request: FeedbackCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FeedbackResponse:
    """Submit thumbs-up/down feedback for a debug session."""
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
            DebugSession.user_id == current_user.id,
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Check for existing feedback — allow only one per session
    existing = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_uuid,
            Feedback.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        # Update existing feedback
        existing.rating = request.rating
        existing.reason = request.reason
        db.commit()
        db.refresh(existing)
        return FeedbackResponse.model_validate(existing)

    feedback = Feedback(
        id=uuid.uuid4(),
        user_id=current_user.id,
        session_id=session_uuid,
        rating=request.rating,
        reason=request.reason,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return FeedbackResponse.model_validate(feedback)


@router.get(
    "/sessions/{session_id}/feedback",
    response_model=FeedbackResponse | None,
)
def get_feedback(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FeedbackResponse | None:
    """Get the current user's feedback for a session, if any."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from err

    feedback = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_uuid,
            Feedback.user_id == current_user.id,
        )
        .first()
    )

    if not feedback:
        return None

    return FeedbackResponse.model_validate(feedback)
