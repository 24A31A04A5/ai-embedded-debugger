from fastapi import FastAPI

from app.routers import health

API_VERSION = "0.1.0"

app = FastAPI(
    title="AI Embedded Debugging Platform API",
    description="Backend API for embedded firmware debugging assistance.",
    version=API_VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health.router, prefix="/v1")
