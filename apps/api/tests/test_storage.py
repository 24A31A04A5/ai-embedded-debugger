import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.services.storage import LocalStorageService, S3StorageService


def test_local_storage_upload_get_delete() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageService(base_dir=tmpdir)
        key = "projects/test-proj/files/abc_test.c"
        content = b"#include <stdio.h>\nint main() { return 0; }\n"

        # Upload
        storage.upload_file(key, content, "text/x-c")

        # Get
        retrieved = storage.get_file(key)
        assert retrieved == content

        # Delete
        storage.delete_file(key)
        with pytest.raises(FileNotFoundError):
            storage.get_file(key)


def test_local_storage_path_traversal_prevention() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageService(base_dir=tmpdir)
        with pytest.raises(ValueError, match="Invalid storage key path traversal"):
            storage.upload_file("../../../etc/passwd", b"bad", "text/plain")


def test_s3_storage_upload_get_delete() -> None:
    with patch("boto3.client") as mock_boto_client:
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"test s3 data"))
        }
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"

        s3_service = S3StorageService()
        s3_service.upload_file("key1", b"test s3 data", "text/plain")
        mock_s3.put_object.assert_called_once_with(
            Bucket=s3_service.bucket_name,
            Key="key1",
            Body=b"test s3 data",
            ContentType="text/plain",
        )

        data = s3_service.get_file("key1")
        assert data == b"test s3 data"

        url = s3_service.get_download_url("key1")
        assert url == "https://s3.example.com/presigned"

        s3_service.delete_file("key1")
        mock_s3.delete_object.assert_called_once_with(
            Bucket=s3_service.bucket_name,
            Key="key1",
        )
