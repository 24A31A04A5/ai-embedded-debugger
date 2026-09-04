"""Add analytics_events table for Phase 6.3 Product Analytics

Revision ID: 006_add_analytics_events
Revises: 005_add_document_chunks
Create Date: 2026-09-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006_add_analytics_events"
down_revision: Union[str, None] = "005_add_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["debug_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analytics_events_event_type"),
        "analytics_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_user_id"),
        "analytics_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_project_id"),
        "analytics_events",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_session_id"),
        "analytics_events",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_success"),
        "analytics_events",
        ["success"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_created_at"),
        "analytics_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_events_project_created",
        "analytics_events",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_events_event_created",
        "analytics_events",
        ["event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_events_event_created", table_name="analytics_events")
    op.drop_index("ix_analytics_events_project_created", table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_created_at"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_success"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_session_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_project_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_user_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_event_type"), table_name="analytics_events")
    op.drop_table("analytics_events")
