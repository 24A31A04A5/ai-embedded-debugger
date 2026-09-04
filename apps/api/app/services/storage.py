from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.config import REPO_ROOT, get_settings


class BaseStorageService(ABC):
    """Abstract interface for object storage."""

    @abstractmethod
    def upload_file(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Upload raw binary data to storage at storage_key."""
        ...

    @abstractmethod
    def get_file(self, storage_key: str) -> bytes:
        """Retrieve raw binary data from storage at storage_key."""
        ...

    @abstractmethod
    def delete_file(self, storage_key: str) -> None:
        """Delete file at storage_key from storage."""
        ...

    @abstractmethod
    def get_download_url(self, storage_key: str, expires_in: int = 3600) -> str | None:
        """Generate a presigned or direct download URL for the file."""
        ...


class LocalStorageService(BaseStorageService):
    """Local filesystem implementation of storage for development/testing."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        settings = get_settings()
        if base_dir is None:
            self.base_dir = REPO_ROOT / settings.local_storage_path
        elif isinstance(base_dir, str):
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, storage_key: str) -> Path:
        # Sanitize and resolve path safely
        safe_key = os.path.normpath(storage_key).lstrip("/\\")
        base_resolved = self.base_dir.resolve()
        target_path = (self.base_dir / safe_key).resolve()

        # Enforce that target_path is strictly inside base_resolved and not the root itself
        try:
            target_path.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Invalid storage key path traversal: {storage_key}")

        if target_path == base_resolved:
            raise ValueError(f"Invalid storage key path traversal: {storage_key}")

        return target_path


    def upload_file(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        file_path = self._get_path(storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)

    def get_file(self, storage_key: str) -> bytes:
        file_path = self._get_path(storage_key)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found in storage: {storage_key}")
        return file_path.read_bytes()

    def delete_file(self, storage_key: str) -> None:
        file_path = self._get_path(storage_key)
        if file_path.exists():
            file_path.unlink()

    def get_download_url(self, storage_key: str, expires_in: int = 3600) -> str | None:
        # In local storage mode, files are served directly via API stream/content endpoint
        return None


class S3StorageService(BaseStorageService):
    """AWS S3 or MinIO S3-compatible object storage service."""

    def __init__(self) -> None:
        settings = get_settings()
        self.bucket_name = settings.s3_bucket_name
        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": settings.s3_region or "us-east-1",
        }
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_access_key_id and settings.s3_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.s3_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.s3_secret_access_key

        self.s3_client = boto3.client(**client_kwargs)

    def upload_file(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=storage_key,
            Body=data,
            ContentType=content_type,
        )

    def get_file(self, storage_key: str) -> bytes:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=storage_key)
            return response["Body"].read()  # type: ignore[no-any-return]
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise FileNotFoundError(f"File not found in S3: {storage_key}") from e
            raise

    def delete_file(self, storage_key: str) -> None:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=storage_key)
        except ClientError:
            pass

    def get_download_url(self, storage_key: str, expires_in: int = 3600) -> str | None:
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": storage_key},
                ExpiresIn=expires_in,
            )
            return str(url)
        except ClientError:
            return None


def get_storage_service() -> BaseStorageService:
    """Factory function returning the configured storage backend service."""
    settings = get_settings()
    if settings.storage_backend.lower() == "s3" and settings.s3_access_key_id:
        return S3StorageService()
    return LocalStorageService()
