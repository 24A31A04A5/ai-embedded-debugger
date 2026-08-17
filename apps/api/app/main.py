from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import debug, feedback, files, health, projects, sessions

API_VERSION = "0.1.0"

app = FastAPI(
    title="AI Embedded Debugging Platform API",
    description="Backend API for embedded firmware debugging assistance.",
    version=API_VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow CORS for Next.js frontend (Phase 1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1")
app.include_router(projects.router, prefix="/v1")
app.include_router(files.router, prefix="/v1")
app.include_router(debug.router, prefix="/v1")
app.include_router(sessions.router, prefix="/v1")
app.include_router(feedback.router, prefix="/v1")

