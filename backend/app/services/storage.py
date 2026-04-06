from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
import os
import aiofiles
from pathlib import Path
import shutil
from contextlib import contextmanager

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class StorageService:
    def __init__(self):
        # Resolve base dir relative to this file: backend/app/services/ -> backend/
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.upload_dir = base_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._create_folder_structure()

    def _create_folder_structure(self):
        """Create standard folder hierarchy for documents."""
        for folder in ["inbox/unprocessed", "inbox/processed", "temp"]:
            (self.upload_dir / folder).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_file(self, file: UploadFile, destination_path: str) -> Tuple[str, Path]:
        """
        Save an uploaded file to storage using chunked streaming.

        Reads the file in 64 KB chunks to avoid loading the entire file into
        memory.  Rejects files that exceed MAX_FILE_SIZE *before* the full
        content has been read — preventing memory spikes from concurrent
        large uploads or malicious oversized payloads.

        Returns:
            (url, absolute_path)  — url is the HTTP URL for the stored file;
                                    absolute_path is the real filesystem Path.
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        dest_dir = self.upload_dir / destination_path
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_path = dest_dir / file.filename

        # Stream file to disk in chunks — reject early if too large
        CHUNK_SIZE = 64 * 1024  # 64 KB
        bytes_written = 0

        try:
            async with aiofiles.open(file_path, "wb") as f:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > MAX_FILE_SIZE:
                        # Stop reading immediately — don't consume the rest
                        break
                    await f.write(chunk)
        except Exception:
            # Clean up partial file on any I/O error
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise

        if bytes_written > MAX_FILE_SIZE:
            # Remove the partially-written file
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)} MB)"
            )

        url = self._path_to_url(f"{destination_path}/{file.filename}")
        return url, file_path

    async def save_file_bytes(
        self, content: bytes, destination: str, filename: str
    ) -> Tuple[str, Path]:
        """Save raw bytes to storage. Returns (url, absolute_path)."""
        file_path = self.upload_dir / destination / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        url = self._path_to_url(f"{destination}/{filename}")
        return url, file_path

    async def get_file_path(self, relative_path: str) -> Path:
        """Resolve a relative path to an absolute filesystem Path."""
        return self.upload_dir / relative_path

    async def get_file_url(self, relative_path: str) -> str:
        """Get HTTP URL for a relative path."""
        return self._path_to_url(relative_path)

    async def move_file(self, current_relative_path: str, new_destination: str) -> str:
        """Move a file; returns the new URL."""
        source = self.upload_dir / current_relative_path
        dest_dir = self.upload_dir / new_destination
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        shutil.move(str(source), str(dest))
        return self._path_to_url(f"{new_destination}/{source.name}")

    async def delete_file(self, relative_path: str) -> bool:
        """Delete a file given its relative path. Returns True if deleted."""
        try:
            full_path = self.upload_dir / relative_path
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file at '{relative_path}': {e}")
            return False

    async def delete_file_by_url(self, url: str) -> bool:
        """
        Delete a file given its stored HTTP URL (s3_url column value).
        Strips the URL prefix and resolves the real filesystem path.
        Returns True if the file was found and deleted.
        """
        try:
            # Strip URL prefix to get relative path, e.g.:
            #   "http://localhost:8000/uploads/inbox/unprocessed/foo.pdf"
            #   -> "inbox/unprocessed/foo.pdf"
            prefix = "http://localhost:8000/uploads/"
            if url.startswith(prefix):
                relative_path = url[len(prefix):]
            else:
                # Fallback: try to extract path after "/uploads/"
                marker = "/uploads/"
                idx = url.find(marker)
                if idx == -1:
                    print(f"Cannot derive filesystem path from URL: {url}")
                    return False
                relative_path = url[idx + len(marker):]

            return await self.delete_file(relative_path)
        except Exception as e:
            print(f"Error deleting file by URL '{url}': {e}")
            return False

    async def get_file_for_processing(self, file_path: str) -> str:
        """
        Get file path for processing (OCR, AI analysis, etc).
        For local storage: returns the absolute path directly.
        For R2: downloads file to temp location and returns temp path.
        
        Args:
            file_path: Relative path (local) or S3 key (R2)
        
        Returns:
            Absolute path to file ready for processing
        """
        # For local storage, just return the absolute path
        abs_path = await self.get_file_path(file_path)
        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return str(abs_path)

    @contextmanager
    def temp_file_context(self, file_path: str):
        """
        Context manager for safely accessing files during processing.
        For local storage: no cleanup needed (file stays in place).
        For R2: downloads to temp, cleans up after block exits.
        
        Usage:
            with storage_service.temp_file_context(file_path) as temp_path:
                process_file(temp_path)
                # Auto-cleanup happens here
        """
        # For local storage, just yield the path
        # No cleanup needed since files stay in place
        try:
            abs_path = self.upload_dir / file_path
            yield str(abs_path)
        except Exception as e:
            print(f"Error in temp_file_context: {e}")
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _path_to_url(self, relative_path: str) -> str:
        return f"http://localhost:8000/uploads/{relative_path}"


# Factory function — priority: s3 > b2 > r2 > local
# To migrate to AWS: set STORAGE_BACKEND=s3 and S3_* env vars.
def get_storage_service():
    from app.core.config import settings

    backend = (settings.STORAGE_BACKEND or "").lower()

    if backend == "s3":
        from app.services.s3_storage import S3StorageService
        return S3StorageService()
    if settings.B2_ENABLED:
        from app.services.b2_storage import B2StorageService
        return B2StorageService()
    if settings.R2_ENABLED:
        from app.services.r2_storage import R2StorageService
        return R2StorageService()
    return StorageService()


# Singleton instance - determined at startup
storage_service = get_storage_service()
