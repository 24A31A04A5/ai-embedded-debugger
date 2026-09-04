from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.analytics import ProjectAnalyticsSummary
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/projects", tags=["analytics"])


def get_project_for_owner(
    project_id: str,
    current_user: User,
    db: Session,
) -> Project:
    """Verify that a project exists and is owned by the current authenticated user."""
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


@router.get(
    "/{project_id}/analytics",
    response_model=ProjectAnalyticsSummary,
)
def get_project_analytics(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> ProjectAnalyticsSummary:
    """Retrieve aggregated usage and diagnostic metrics for an owned project."""
    project = get_project_for_owner(project_id, current_user, db)
    return AnalyticsService.get_project_summary(
        db=db,
        project_id=project.id,
        time_window_days=days,
    )
