"""Request correlation ID middleware for distributed tracing and observability."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import request_id_ctx

logger = logging.getLogger("app.access")

# Allowed characters for incoming correlation IDs: 8-64 alphanumeric, dash, underscore
_SAFE_REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def is_safe_request_id(request_id: str | None) -> bool:
    """Validate that incoming client request ID contains only safe alphanumeric/uuid characters."""
    if not request_id:
        return False
    return bool(_SAFE_REQUEST_ID_REGEX.match(request_id.strip()))


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Assigns or preserves a safe request correlation ID and measures request latency."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        settings = get_settings()
        header_name = getattr(settings, "request_id_header_name", "X-Request-ID")

        # Inspect incoming request headers for correlation IDs
        raw_req_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")

        if is_safe_request_id(raw_req_id):
            request_id = raw_req_id.strip()  # type: ignore[union-attr]
        else:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Inject request ID into response headers
            response.headers[header_name] = request_id

            # Avoid logging redundant health check pings at INFO level if desired, or log cleanly
            logger.info(
                "%s %s -> %s (%.2fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

            return response
        finally:
            request_id_ctx.reset(token)
