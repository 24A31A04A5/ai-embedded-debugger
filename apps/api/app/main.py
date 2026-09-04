import logging
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.correlation import RequestCorrelationMiddleware
from app.core.error_monitoring import get_error_tracker
from app.core.logging import get_request_id, setup_logging
from app.core.security import sanitize_error_detail, sanitize_secrets
from app.routers import analytics, debug, documents, feedback, files, health, projects, sessions

API_VERSION = "0.1.0"

settings = get_settings()
setup_logging(settings.log_level)
is_production = settings.app_env.lower() == "production"

app = FastAPI(
    title="AI Embedded Debugging Platform API",
    description="Backend API for embedded firmware debugging assistance.",
    version=API_VERSION,
    openapi_url="/openapi.json" if not is_production else None,
    docs_url="/docs" if not is_production else None,
    redoc_url="/redoc" if not is_production else None,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject standard production security headers on all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


# Correlation middleware wraps the application to ensure all responses get X-Request-ID
app.add_middleware(RequestCorrelationMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Configurable CORS
raw_origins = settings.cors_origins
if isinstance(raw_origins, list):
    allowed_origins = raw_origins
else:
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Production-safe global exception handler preventing leakage of traces or credentials."""
    # Preserve standard HTTP status exceptions and validation responses
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)

    # Capture diagnostic information internally
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    tracker = get_error_tracker()
    tracker.capture_exception(
        exc,
        context={
            "path": request.url.path,
            "method": request.method,
            "request_id": req_id,
        },
    )

    current_settings = get_settings()
    if current_settings.expose_error_details:
        detail_msg = sanitize_secrets(str(exc))
    else:
        detail_msg = "An unexpected error occurred. Please try again later."

    content = {
        "detail": detail_msg,
        "request_id": req_id,
    }
    header_name = getattr(current_settings, "request_id_header_name", "X-Request-ID")
    headers = {header_name: req_id} if req_id else {}

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        headers=headers,
    )


# Root probe endpoints for deployment orchestrators
app.include_router(health.router)

# Versioned API endpoints
app.include_router(health.router, prefix="/v1")
app.include_router(projects.router, prefix="/v1")
app.include_router(files.router, prefix="/v1")
app.include_router(documents.router, prefix="/v1")
app.include_router(debug.router, prefix="/v1")
app.include_router(sessions.router, prefix="/v1")
app.include_router(feedback.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")
