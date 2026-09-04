"""In-memory sliding-window rate limiter and abuse protection for FastAPI."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings


class InMemoryRateLimiter:
    """Thread-safe, in-memory sliding window rate limiter without external infrastructure."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}
        self._lock = Lock()

    def is_rate_limited(
        self, key: str, limit: int, window_seconds: int = 60
    ) -> tuple[bool, int]:
        """Check if request for key exceeds limit in window_seconds.

        Returns (is_limited, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._requests.get(key, [])
            # Evict timestamps outside the sliding window
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= limit:
                # Rate limit exceeded: calculate seconds until the oldest request expires
                oldest = timestamps[0] if timestamps else now
                retry_after = max(1, int(oldest + window_seconds - now) + 1)
                self._requests[key] = timestamps
                return True, retry_after

            timestamps.append(now)
            self._requests[key] = timestamps
            return False, 0

    def reset(self) -> None:
        """Clear all recorded request timestamps (for testing and maintenance)."""
        with self._lock:
            self._requests.clear()


# Global rate limiter instance
_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """Dependency provider returning the rate limiter singleton."""
    return _limiter


def get_client_identifier(request: Request) -> str:
    """Extract a stable identifier for rate limiting based on auth token or client IP."""
    auth_header = request.headers.get("authorization")
    if auth_header and len(auth_header) > 10:
        # Use truncated hash of authorization header for authenticated clients
        token_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:16]
        return f"auth:{token_hash}"

    # Fallback to forwarded IP or direct client host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"

    if request.client and request.client.host:
        return f"ip:{request.client.host}"

    return "ip:unknown"


class RateLimitChecker:
    """FastAPI dependency for endpoint-level rate limit enforcement."""

    def __init__(self, bucket: str, get_limit: Callable[[], int], window_seconds: int = 60) -> None:
        self.bucket = bucket
        self.get_limit = get_limit
        self.window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        limiter: Annotated[InMemoryRateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return

        client_id = get_client_identifier(request)
        key = f"{self.bucket}:{client_id}"
        limit = self.get_limit()

        # If limit is 0 or negative, skip limiting
        if limit <= 0:
            return

        is_limited, retry_after = limiter.is_rate_limited(
            key=key,
            limit=limit,
            window_seconds=self.window_seconds,
        )
        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again later.",
                headers={"Retry-After": str(retry_after)},
            )


# Pre-configured rate limiting dependencies
check_ai_rate_limit = RateLimitChecker(
    bucket="ai",
    get_limit=lambda: get_settings().rate_limit_ai_requests_per_minute,
    window_seconds=60,
)

check_upload_rate_limit = RateLimitChecker(
    bucket="upload",
    get_limit=lambda: get_settings().rate_limit_upload_requests_per_minute,
    window_seconds=60,
)

check_search_rate_limit = RateLimitChecker(
    bucket="search",
    get_limit=lambda: get_settings().rate_limit_general_requests_per_minute,
    window_seconds=60,
)
