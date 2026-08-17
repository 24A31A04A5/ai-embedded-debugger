import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
def get_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Project]:
    """Get all active projects for the current user."""
    projects = (
        db.query(Project)
        .filter(Project.owner_id == current_user.id)
        .filter(Project.status == "active")
        .order_by(Project.created_at.desc())
        .all()
    )
    return projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Project:
    """Create a new project for the current user."""
    new_project = Project(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        name=project_in.name,
        description=project_in.description,
        status="active",
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project
