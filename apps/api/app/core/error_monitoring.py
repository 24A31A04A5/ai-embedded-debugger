"""Error tracking abstraction boundary for production observability."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_request_id
from app.core.security import sanitize_secrets

logger = logging.getLogger("app.error_tracker")


class BaseErrorTracker(ABC):
    """Abstract interface for error tracking and APM integrations."""

    @abstractmethod
    def capture_exception(
        self,
        exc: Exception,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Capture an exception and return an error tracking event ID."""
        pass

    @abstractmethod
    def capture_message(
        self,
        message: str,
        level: str = "info",
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Capture an informational or warning event."""
        pass


class LocalErrorTracker(BaseErrorTracker):
    """Production-safe local error tracking implementation without external dependencies."""

    def capture_exception(
        self,
        exc: Exception,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        try:
            req_id = get_request_id()
            safe_message = sanitize_secrets(str(exc))
            error_type = type(exc).__name__

            extra_info = ""
            if context:
                safe_context = {
                    k: sanitize_secrets(str(v))
                    for k, v in context.items()
                    if not any(secret in k.lower() for secret in ("token", "key", "password", "secret", "auth"))
                }
                extra_info = f" | context: {safe_context}"

            logger.error(
                "Captured Exception [%s]: %s (request_id=%s)%s",
                error_type,
                safe_message,
                req_id or "none",
                extra_info,
                exc_info=exc,
            )
            return req_id or None
        except Exception:
            # Error tracking must never crash the caller
            return None

    def capture_message(
        self,
        message: str,
        level: str = "info",
        context: dict[str, Any] | None = None,
    ) -> str | None:
        try:
            req_id = get_request_id()
            safe_msg = sanitize_secrets(message)
            log_fn = getattr(logger, level.lower(), logger.info)
            log_fn("Captured Message: %s (request_id=%s)", safe_msg, req_id or "none")
            return req_id or None
        except Exception:
            return None


_default_tracker = LocalErrorTracker()


def get_error_tracker() -> BaseErrorTracker:
    """Dependency provider returning the active error tracking singleton."""
    return _default_tracker
