# =============================================================================
# FastAPI Backend — Production Container Image
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definitions
COPY pyproject.toml README.md ./
COPY apps/api ./apps/api
COPY db ./db

# Install application and dependencies into wheels/site-packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# -----------------------------------------------------------------------------
# Production runtime stage
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies (e.g. curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy installed Python packages and entrypoints from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source, migrations, and alembic config
COPY --chown=appuser:appgroup apps/api ./apps/api
COPY --chown=appuser:appgroup db ./db
COPY --chown=appuser:appgroup pyproject.toml README.md ./

# Create storage directory with correct permissions
RUN mkdir -p /app/storage_data && chown -R appuser:appgroup /app/storage_data

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    PORT=8000

EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production start command (2 workers default, configurable)
CMD ["uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
