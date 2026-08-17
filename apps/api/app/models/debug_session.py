from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.debug_message import DebugMessage
    from app.models.feedback import Feedback
    from app.models.project import Project
    from app.models.user import User


class DebugSession(Base):
    """A debugging session scoped to a project and user.

    Tracks the conversation history (messages) and associated feedback
    for a single debugging analysis workflow.
    """

    __tablename__ = "debug_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship("Project", back_populates="debug_sessions")
    user: Mapped[User] = relationship("User", back_populates="debug_sessions")
    messages: Mapped[list[DebugMessage]] = relationship(
        "DebugMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DebugMessage.created_at",
    )
    feedbacks: Mapped[list[Feedback]] = relationship(
        "Feedback",
        back_populates="session",
        cascade="all, delete-orphan",
    )
