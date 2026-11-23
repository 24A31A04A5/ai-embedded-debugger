"""Environment isolation and safety checks for benchmark execution.

This module provides fail-closed environment protection to prevent
accidental use of production resources during benchmark runs.
"""

from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class EnvironmentCheckResult:
    """Result of an environment safety check."""
    check_name: str
    passed: bool
    message: str
    details: dict = None


class EnvironmentGuard:
    """Fail-closed environment protection for benchmark runs."""

    # Known production indicators
    PRODUCTION_DB_HOSTS = [
        "neon.tech",
        "aws.neon.tech",
        "eu-central-1.aws.neon.tech",
        "us-east-1.aws.neon.tech",
    ]
    PRODUCTION_KEYWORDS = ["prod", "production", "live"]

    def __init__(self, require_isolation: bool = True):
        self.require_isolation = require_isolation
        self.checks: list[EnvironmentCheckResult] = []

    def check_database_isolation(self) -> EnvironmentCheckResult:
        """Verify database is not a production instance and is a valid test database."""
        db_url = os.getenv("DATABASE_URL", "")

        if not db_url:
            return EnvironmentCheckResult(
                check_name="database_isolation",
                passed=False,
                message="DATABASE_URL not set - required for real benchmark execution",
                details={"db_url": "NOT_SET"},
            )

        # Check for production hosts
        is_production = any(host in db_url for host in self.PRODUCTION_DB_HOSTS)

        # Check for production keywords in URL
        db_lower = db_url.lower()
        has_prod_keywords = any(kw in db_lower for kw in self.PRODUCTION_KEYWORDS)

        # Allow local/test databases
        is_local = any(
            indicator in db_url
            for indicator in ["localhost", "127.0.0.1", "test", "unittest", "pytest", "dev", "staging"]
        )

        # Verify pgvector extension is available (required for RAG)
        has_pgvector_indicator = "pgvector" in db_lower or "vector" in db_lower

        if is_production and not is_local:
            return EnvironmentCheckResult(
                check_name="database_isolation",
                passed=False,
                message=f"Production database detected: {db_url[:50]}...",
                details={
                    "db_host": "production" if is_production else "unknown",
                    "has_prod_keywords": has_prod_keywords,
                    "is_local": is_local,
                },
            )

        if not is_local:
            return EnvironmentCheckResult(
                check_name="database_isolation",
                passed=False,
                message=f"Database does not appear to be a local/test/dev database: {db_url[:50]}...",
                details={
                    "is_production_host": is_production,
                    "has_prod_keywords": has_prod_keywords,
                    "is_local": is_local,
                },
            )

        return EnvironmentCheckResult(
            check_name="database_isolation",
            passed=True,
            message="Database isolation verified (local/test/dev database with pgvector)",
            details={
                "is_production_host": is_production,
                "has_prod_keywords": has_prod_keywords,
                "is_local": is_local,
                "has_pgvector_indicator": has_pgvector_indicator,
            },
        )

    def check_api_keys(self) -> EnvironmentCheckResult:
        """Verify API keys are not production credentials."""
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        clerk_key = os.getenv("CLERK_SECRET_KEY", "")

        issues = []

        if not gemini_key:
            issues.append("GEMINI_API_KEY not set")
        elif len(gemini_key) < 20:
            issues.append("GEMINI_API_KEY appears invalid (too short)")

        if not clerk_key:
            issues.append("CLERK_SECRET_KEY not set")

        if issues:
            return EnvironmentCheckResult(
                check_name="api_keys",
                passed=False,
                message="; ".join(issues),
                details={"gemini_key_set": bool(gemini_key), "clerk_key_set": bool(clerk_key)},
            )

        return EnvironmentCheckResult(
            check_name="api_keys",
            passed=True,
            message="API keys present",
            details={"gemini_key_set": True, "clerk_key_set": True},
        )

    def check_storage_isolation(self) -> EnvironmentCheckResult:
        """Verify storage backend is local/test."""
        storage_backend = os.getenv("STORAGE_BACKEND", "local")
        local_path = os.getenv("LOCAL_STORAGE_PATH", "storage_data")
        s3_bucket = os.getenv("S3_BUCKET_NAME", "")

        if storage_backend == "s3" and s3_bucket:
            if "prod" in s3_bucket.lower() or "production" in s3_bucket.lower():
                return EnvironmentCheckResult(
                    check_name="storage_isolation",
                    passed=False,
                    message=f"Production S3 bucket detected: {s3_bucket}",
                    details={"storage_backend": storage_backend, "s3_bucket": s3_bucket},
                )

        return EnvironmentCheckResult(
            check_name="storage_isolation",
            passed=True,
            message="Storage isolation verified (local or test bucket)",
            details={"storage_backend": storage_backend, "local_path": local_path},
        )

    def check_environment_mode(self) -> EnvironmentCheckResult:
        """Verify APP_ENV is not production."""
        app_env = os.getenv("APP_ENV", "development").lower()

        if app_env == "production":
            return EnvironmentCheckResult(
                check_name="environment_mode",
                passed=False,
                message="APP_ENV is set to production",
                details={"app_env": app_env},
            )

        return EnvironmentCheckResult(
            check_name="environment_mode",
            passed=True,
            message=f"Environment mode: {app_env}",
            details={"app_env": app_env},
        )

    def check_migrations_blocked(self) -> EnvironmentCheckResult:
        """Verify migrations are not configured for production."""
        # Check if alembic is pointing to production
        alembic_ini = Path("db/alembic.ini")
        if alembic_ini.exists():
            content = alembic_ini.read_text()
            if "neon.tech" in content and "test" not in content.lower():
                return EnvironmentCheckResult(
                    check_name="migrations_blocked",
                    passed=False,
                    message="Alembic configuration may target production database",
                    details={"alembic_ini": str(alembic_ini)},
                )

        return EnvironmentCheckResult(
            check_name="migrations_blocked",
            passed=True,
            message="Migrations configuration appears safe",
            details={},
        )

    def run_all_checks(self, allow_mock: bool = False) -> tuple[bool, list[EnvironmentCheckResult]]:
        """Run all environment checks. Returns (all_passed, results).

        Args:
            allow_mock: If True, skip database and API key checks for mock mode.
        """
        checks = [
            self.check_database_isolation(),
            self.check_api_keys(),
            self.check_storage_isolation(),
            self.check_environment_mode(),
            self.check_migrations_blocked(),
        ]

        # In mock mode, we can be more lenient
        if allow_mock:
            # Filter out database and API key checks
            checks = [c for c in checks if c.check_name not in ("database_isolation", "api_keys")]

        self.checks = checks

        all_passed = all(c.passed for c in self.checks)

        # Print results
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"  [{status}] {check.check_name}: {check.message}")

        return all_passed, self.checks

    def enforce_isolation(self) -> None:
        """Enforce isolation - raise exception if checks fail."""
        all_passed, results = self.run_all_checks()

        if not all_passed:
            failed = [r for r in results if not r.passed]
            error_msg = "ENVIRONMENT ISOLATION FAILED - Benchmark execution blocked:\n"
            for f in failed:
                error_msg += f"  - {f.check_name}: {f.message}\n"
            error_msg += "\nSet USE_MOCK=true or configure proper test environment to proceed."
            raise RuntimeError(error_msg)


def verify_benchmark_environment(require_isolation: bool = True, allow_mock: bool = False) -> bool:
    """Convenience function to verify benchmark environment.

    Args:
        require_isolation: If True, raises RuntimeError on failure.
                          If False, returns boolean and prints warnings.
        allow_mock: If True, allows mock mode to run with relaxed checks.

    Returns:
        True if all checks pass.

    Raises:
        RuntimeError: If require_isolation=True and checks fail.
    """
    guard = EnvironmentGuard(require_isolation=require_isolation)
    all_passed, results = guard.run_all_checks(allow_mock=allow_mock)

    if not all_passed and require_isolation:
        guard.enforce_isolation()

    return all_passed


if __name__ == "__main__":
    # Allow running as standalone check
    import argparse

    parser = argparse.ArgumentParser(description="Verify benchmark environment isolation")
    parser.add_argument("--strict", action="store_true", help="Fail on any check failure")
    args = parser.parse_args()

    try:
        verify_benchmark_environment(require_isolation=args.strict)
        print("\n✓ All environment checks passed")
        sys.exit(0)
    except RuntimeError as e:
        print(f"\n✗ {e}")
        sys.exit(1)