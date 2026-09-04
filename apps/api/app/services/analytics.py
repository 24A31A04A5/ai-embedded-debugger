from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analytics_event import AnalyticsEvent
from app.schemas.analytics import AnalyticsEventType, ProjectAnalyticsSummary

logger = logging.getLogger(__name__)

# Keys that must NEVER be stored in analytics metadata to preserve user privacy and IP protection
DISALLOWED_METADATA_KEYS = {
    "code",
    "firmware_code",
    "source_code",
    "compiler_output",
    "serial_logs",
    "logs",
    "log_lines",
    "document_content",
    "content",
    "user_question",
    "question",
    "prompt",
    "api_key",
    "token",
    "password",
    "secret",
    "authorization",
}


def sanitize_analytics_metadata(raw_metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip any source code, raw logs, prompts, or sensitive credentials."""
    if not raw_metadata:
        return None

    cleaned: dict[str, Any] = {}
    for key, value in raw_metadata.items():
        lower_key = key.lower()
        if lower_key in DISALLOWED_METADATA_KEYS:
            continue
        if any(substr in lower_key for substr in ("password", "secret", "token", "prompt", "source_code")):
            continue
        # Truncate string values to prevent accidental log dumping
        if isinstance(value, str) and len(value) > 256:
            cleaned[key] = value[:256] + "..."
        else:
            cleaned[key] = value

    return cleaned if cleaned else None


class AnalyticsService:
    """Lightweight product analytics service with privacy and resilience guarantees."""

    @staticmethod
    def track_event(
        db: Session,
        event_type: str | AnalyticsEventType,
        *,
        user_id: uuid.UUID | str | None = None,
        project_id: uuid.UUID | str | None = None,
        session_id: uuid.UUID | str | None = None,
        success: bool = True,
        latency_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalyticsEvent | None:
        """Record an analytics event safely. Never raises exceptions to callers."""
        settings = get_settings()
        if not settings.analytics_enabled:
            return None

        try:
            # Coerce string IDs to UUIDs if valid
            clean_user_id = uuid.UUID(str(user_id)) if user_id else None
            clean_project_id = uuid.UUID(str(project_id)) if project_id else None
            clean_session_id = uuid.UUID(str(session_id)) if session_id else None

            type_str = event_type.value if isinstance(event_type, AnalyticsEventType) else str(event_type)
            clean_meta = sanitize_analytics_metadata(metadata)

            event = AnalyticsEvent(
                id=uuid.uuid4(),
                event_type=type_str,
                user_id=clean_user_id,
                project_id=clean_project_id,
                session_id=clean_session_id,
                success=success,
                latency_ms=latency_ms,
                metadata_json=clean_meta,
            )

            db.add(event)
            db.commit()
            return event
        except Exception as exc:
            # Analytics failures MUST NEVER break the main user flow
            logger.warning("Failed to record analytics event '%s': %s", event_type, exc)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def get_project_summary(
        db: Session,
        project_id: uuid.UUID,
        time_window_days: int = 30,
    ) -> ProjectAnalyticsSummary:
        """Aggregate product metrics for a given project workspace."""
        cutoff = datetime.now(UTC) - timedelta(days=time_window_days)

        # Query all events in window for this project
        events = (
            db.query(AnalyticsEvent)
            .filter(
                AnalyticsEvent.project_id == project_id,
                AnalyticsEvent.created_at >= cutoff,
            )
            .all()
        )

        event_counts: dict[str, int] = {}
        total_debug = 0
        successful_debug = 0
        failed_debug = 0
        debug_latencies: list[int] = []
        files_uploaded = 0
        documents_uploaded = 0
        sessions_created = 0
        feedback_count = 0
        positive_feedback_count = 0

        for e in events:
            event_counts[e.event_type] = event_counts.get(e.event_type, 0) + 1

            if e.event_type == AnalyticsEventType.DEBUG_REQUEST_STARTED.value:
                total_debug += 1
            elif e.event_type == AnalyticsEventType.DEBUG_REQUEST_COMPLETED.value:
                successful_debug += 1
                if e.latency_ms is not None:
                    debug_latencies.append(e.latency_ms)
            elif e.event_type == AnalyticsEventType.DEBUG_REQUEST_FAILED.value:
                failed_debug += 1
            elif e.event_type == AnalyticsEventType.FILE_UPLOADED.value:
                files_uploaded += 1
            elif e.event_type == AnalyticsEventType.DOCUMENT_UPLOADED.value:
                documents_uploaded += 1
            elif e.event_type == AnalyticsEventType.SESSION_CREATED.value:
                sessions_created += 1
            elif e.event_type == AnalyticsEventType.FEEDBACK_SUBMITTED.value:
                feedback_count += 1
                if e.metadata_json and e.metadata_json.get("rating", 0) > 0:
                    positive_feedback_count += 1

        avg_latency = (
            round(sum(debug_latencies) / len(debug_latencies), 1)
            if debug_latencies
            else None
        )

        return ProjectAnalyticsSummary(
            project_id=project_id,
            time_window_days=time_window_days,
            total_debug_requests=total_debug,
            successful_debug_requests=successful_debug,
            failed_debug_requests=failed_debug,
            avg_debug_latency_ms=avg_latency,
            total_files_uploaded=files_uploaded,
            total_documents_uploaded=documents_uploaded,
            total_sessions_created=sessions_created,
            feedback_count=feedback_count,
            positive_feedback_count=positive_feedback_count,
            event_counts=event_counts,
        )
