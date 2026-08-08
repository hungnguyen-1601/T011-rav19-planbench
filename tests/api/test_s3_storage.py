"""Unit tests for S3ModelStorage implementation."""

from unittest.mock import MagicMock, patch
import pytest

from planbench_api.model_storage import S3ModelStorage, UploadTooLarge


def test_s3_storage_save_and_checksum():
    """Test S3ModelStorage save and checksum calculation."""
    mock_boto3 = MagicMock()
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        storage = S3ModelStorage(bucket_name="test-bucket", local_cache_root="/tmp/s3_cache")
        source = [b"test ", b"content"]

        stored_file = storage.save(key="models/test.zip", source=iter(source), max_bytes=1000)

        assert stored_file.storage_key == "models/test.zip"
        assert stored_file.size_bytes == 12
        assert len(stored_file.checksum) == 64  # SHA-256 hex string length
        assert mock_s3_client.put_object.called


def test_s3_storage_save_too_large():
    """Test S3ModelStorage raises UploadTooLarge when payload exceeds limit."""
    mock_boto3 = MagicMock()
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        storage = S3ModelStorage(bucket_name="test-bucket", local_cache_root="/tmp/s3_cache")
        source = [b"a" * 50, b"b" * 60]

        with pytest.raises(UploadTooLarge):
            storage.save(key="models/large.zip", source=iter(source), max_bytes=100)


def test_s3_storage_exists_and_delete():
    """Test S3ModelStorage exists check and delete."""
    mock_boto3 = MagicMock()
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        storage = S3ModelStorage(bucket_name="test-bucket", local_cache_root="/tmp/s3_cache")

        mock_s3_client.head_object.return_value = {}
        assert storage.exists("models/test.zip") is True

        storage.delete("models/test.zip")
        assert mock_s3_client.delete_object.called
