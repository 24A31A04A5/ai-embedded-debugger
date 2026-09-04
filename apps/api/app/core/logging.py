"""Centralized structured logging and secret sanitization for the API."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.security import sanitize_secrets

# Request correlation ID context variable
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Retrieve the current request correlation ID from context."""
    return request_id_ctx.get() or ""


class StructuredLogFormatter(logging.Formatter):
    """Log formatter that includes timestamp, level, request ID, and redacts secrets."""

    def format(self, record: logging.LogRecord) -> str:
        # Generate ISO-8601 UTC timestamp
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"
        level = record.levelname
        logger_name = record.name
        req_id = get_request_id() or getattr(record, "request_id", "-")

        # Sanitize message to ensure zero credentials, tokens, or API keys are logged
        raw_message = record.getMessage()
        sanitized_message = sanitize_secrets(raw_message)

        # Base structured prefix
        log_line = f"[{timestamp}] [{level:<7}] [req:{req_id}] [{logger_name}] {sanitized_message}"

        # If an exception is attached, sanitize and append its formatted traceback
        if record.exc_info:
            exc_text = super().formatException(record.exc_info)
            sanitized_exc = sanitize_secrets(exc_text)
            log_line = f"{log_line}\n{sanitized_exc}"

        return log_line


def setup_logging(log_level: str | None = None) -> None:
    """Configure structured logging across the application."""
    from app.core.config import get_settings

    resolved_level = (log_level or get_settings().log_level).upper()
    numeric_level = getattr(logging, resolved_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Check if a StructuredLogFormatter handler is already attached
    for handler in root_logger.handlers:
        if isinstance(handler.formatter, StructuredLogFormatter):
            handler.setLevel(numeric_level)
            return

    # Add stdout stream handler with structured formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(StructuredLogFormatter())
    root_logger.addHandler(handler)
