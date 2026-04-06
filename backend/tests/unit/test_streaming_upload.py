"""
Unit tests for the streaming upload functionality in StorageService.
Tests chunked read behavior and early size rejection.
These tests don't require a running database.
"""

import asyncio
import pytest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, UploadFile


# ── Helpers ─────────────────────────────────────────────────────────────

class FakeUploadFile:
    """Fake UploadFile that simulates reading in chunks."""

    def __init__(self, data: bytes, filename: str = "test.pdf"):
        self.filename = filename
        self._data = data
        self._position = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._data[self._position:]
            self._position = len(self._data)
            return chunk
        chunk = self._data[self._position:self._position + size]
        self._position += len(chunk)
        return chunk


# ── Tests ───────────────────────────────────────────────────────────────

@pytest.fixture
def storage_service(tmp_path):
    """Create a StorageService with a temp directory for testing."""
    from app.services.storage import StorageService
    service = StorageService.__new__(StorageService)
    service.upload_dir = tmp_path / "uploads"
    service.upload_dir.mkdir(parents=True, exist_ok=True)
    return service


@pytest.mark.asyncio
async def test_upload_small_file_succeeds(storage_service, tmp_path):
    """A file under the size limit should be saved successfully."""
    data = b"Hello, this is a small test file." * 100  # ~3.2 KB
    fake_file = FakeUploadFile(data, filename="small.pdf")

    url, file_path = await storage_service.upload_file(fake_file, "test/path")

    assert file_path.exists()
    assert file_path.read_bytes() == data
    assert "test/path/small.pdf" in url


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file_early(storage_service):
    """A file exceeding MAX_FILE_SIZE should be rejected and no file should remain."""
    from app.services.storage import MAX_FILE_SIZE

    # Create data that exceeds the limit
    data = b"x" * (MAX_FILE_SIZE + 1024)
    fake_file = FakeUploadFile(data, filename="huge.pdf")

    with pytest.raises(HTTPException) as exc_info:
        await storage_service.upload_file(fake_file, "test/path")

    assert exc_info.value.status_code == 400
    assert "too large" in exc_info.value.detail.lower()

    # Verify no partial file remains
    possible_path = storage_service.upload_dir / "test/path" / "huge.pdf"
    assert not possible_path.exists()


@pytest.mark.asyncio
async def test_upload_rejects_exactly_at_limit(storage_service):
    """A file exactly at MAX_FILE_SIZE should be accepted (boundary case)."""
    from app.services.storage import MAX_FILE_SIZE

    data = b"x" * MAX_FILE_SIZE
    fake_file = FakeUploadFile(data, filename="exact.pdf")

    url, file_path = await storage_service.upload_file(fake_file, "test/path")

    assert file_path.exists()
    assert len(file_path.read_bytes()) == MAX_FILE_SIZE


@pytest.mark.asyncio
async def test_upload_rejects_invalid_extension(storage_service):
    """Files with disallowed extensions should be rejected."""
    fake_file = FakeUploadFile(b"data", filename="malware.exe")

    with pytest.raises(HTTPException) as exc_info:
        await storage_service.upload_file(fake_file, "test/path")

    assert exc_info.value.status_code == 400
    assert "not allowed" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_upload_rejects_empty_filename(storage_service):
    """Files with no filename should be rejected."""
    fake_file = FakeUploadFile(b"data", filename="")
    fake_file.filename = None

    with pytest.raises(HTTPException) as exc_info:
        await storage_service.upload_file(fake_file, "test/path")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_chunked_reading(storage_service):
    """Verify that the upload reads in chunks (64KB), not all at once."""
    chunk_size = 64 * 1024  # 64 KB
    # Create a file larger than one chunk but under the limit
    data = b"y" * (chunk_size * 3 + 1000)  # ~193 KB
    fake_file = FakeUploadFile(data, filename="chunked.pdf")

    url, file_path = await storage_service.upload_file(fake_file, "test/path")

    assert file_path.exists()
    assert file_path.read_bytes() == data


@pytest.mark.asyncio
async def test_upload_creates_destination_directory(storage_service):
    """Upload should create destination directory if it doesn't exist."""
    data = b"content"
    fake_file = FakeUploadFile(data, filename="nested.pdf")

    url, file_path = await storage_service.upload_file(fake_file, "deep/nested/path")

    assert file_path.exists()
    assert file_path.parent.name == "path"
