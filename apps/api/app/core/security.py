"""Security utilities for input sanitization, path traversal prevention, and secret redaction."""

from __future__ import annotations

import re
from pathlib import Path

# Common patterns for secrets, tokens, and credentials
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Google / Gemini API keys (starts with AIzaSy...)
    (re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"), "[REDACTED_GEMINI_KEY]"),
    # Generic api_key= / key= query parameters or assignments
    (re.compile(r"(api[_-]?key\s*[:=]\s*['\"]?)[A-Za-z0-9_\-\.]{8,}['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
    # Clerk secret keys (sk_test_..., sk_live_..., or clerk_test_...)
    (re.compile(r"(?:clerk_(?:test|live)_|sk_(?:test|live)_)[A-Za-z0-9]{20,}"), "[REDACTED_CLERK_KEY]"),
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{16,}", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    # AWS access key IDs (AKIA...)
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    # AWS secret access keys in key=... or secret=... patterns
    (re.compile(r"((?:aws_secret_access_key|secret_key|password|secret)\s*[:=]\s*['\"]?)[A-Za-z0-9/+=]{16,}['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
]

# Windows reserved device names
_RESERVED_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(filename: str | None, default: str = "file") -> str:
    """Sanitize an untrusted user-supplied filename to prevent path traversal and unsafe storage.

    - Strips directory components across both POSIX (/) and Windows (\\) separators.
    - Removes null bytes and non-printable control characters.
    - Strips leading and trailing dots and whitespace.
    - Neutralizes Windows reserved device names (CON, PRN, AUX, etc.).
    - Truncates to a maximum length of 255 characters.
    """
    if not filename:
        return default

    # Normalize separators and take the final component
    cleaned = filename.replace("\\", "/").rstrip("/")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]

    # Remove null bytes and non-printable control characters (ASCII 0-31, 127-159)
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)

    # Strip dangerous characters, leading/trailing dots and spaces
    cleaned = cleaned.strip(" .")

    if not cleaned:
        return default

    # Neutralize Windows reserved device names
    base_stem = cleaned.split(".")[0].upper()
    if base_stem in _RESERVED_DEVICE_NAMES:
        cleaned = f"safe_{cleaned}"

    # Truncate to maximum 255 characters while preserving extension if possible
    if len(cleaned) > 255:
        p = Path(cleaned)
        ext = p.suffix[:20]
        max_stem_len = 255 - len(ext)
        cleaned = f"{p.stem[:max_stem_len]}{ext}"

    return cleaned if cleaned else default


def sanitize_secrets(text: str | None) -> str:
    """Redact sensitive API keys, tokens, and credentials from logs and error messages."""
    if not text:
        return ""

    sanitized = text
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def sanitize_error_detail(error: Exception | str, default: str = "Operation failed.") -> str:
    """Produce a safe error message suitable for client-facing API responses.

    Prevents internal stack, path, host, or implementation details from leaking.
    """
    error_str = str(error) if error else default
    lower = error_str.lower()

    # Preserve specific expected user-friendly messages for Gemini API key errors
    if "api_key" in lower or "api key" in lower or ("gemini" in lower and "key" in lower):
        return "Gemini API connection or authentication failed."

    # Return safe default message for all other unexpected exceptions
    return default


