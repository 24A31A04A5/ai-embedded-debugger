from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.routers import analytics, debug, documents, feedback, files, health, projects, sessions

API_VERSION = "0.1.0"

settings = get_settings()
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

app.include_router(health.router, prefix="/v1")
app.include_router(projects.router, prefix="/v1")
app.include_router(files.router, prefix="/v1")
app.include_router(documents.router, prefix="/v1")
app.include_router(debug.router, prefix="/v1")
app.include_router(sessions.router, prefix="/v1")
app.include_router(feedback.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")



