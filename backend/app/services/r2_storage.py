"""
Cloudflare R2 Storage Service
Provides S3-compatible interface for storing files in Cloudflare R2
"""
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging
import tempfile
import shutil
from contextlib import contextmanager

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class R2StorageService:
    """
    Storage service for Cloudflare R2.
    Uses boto3 (AWS SDK) to interact with R2's S3-compatible API.
    """
    
    def __init__(self):
        if not settings.R2_ENABLED:
            raise ValueError("R2 is not enabled. Set R2_ENABLED=true in .env")
        
        self.bucket_name = settings.R2_BUCKET_NAME
        self.public_url_base = settings.R2_PUBLIC_URL.rstrip('/') if settings.R2_PUBLIC_URL else None
        
        # Initialize S3 client for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name='auto',  # Required for R2
        )
        
        logger.info(f"R2StorageService initialized with bucket: {self.bucket_name}")

    # ------------------------------------------------------------------
    # Public API (matches StorageService interface)
    # ------------------------------------------------------------------

    async def upload_file(self, file: UploadFile, destination_path: str) -> Tuple[str, str]:
        """
        Save an uploaded file to R2.

        Args:
            file: FastAPI UploadFile
            destination_path: Relative path in bucket (e.g., "cases/123/documents")

        Returns:
            (url, s3_key) — url is the public URL for accessing the file;
                           s3_key is the full object path in R2
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # Read file content
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

        # Build S3 key (full path in bucket)
        s3_key = f"{destination_path}/{file.filename}"
        
        try:
            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=file.content_type or 'application/octet-stream',
            )
            logger.info(f"File uploaded to R2: {s3_key}")
        except ClientError as e:
            logger.error(f"R2 upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"R2 upload failed: {str(e)}"
            )

        # Generate public URL
        url = self._key_to_url(s3_key)
        return url, s3_key

    async def save_file_bytes(
        self, content: bytes, destination: str, filename: str
    ) -> Tuple[str, str]:
        """Save raw bytes to R2. Returns (url, s3_key)."""
        s3_key = f"{destination}/{filename}"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType='application/octet-stream',
            )
            logger.info(f"Bytes saved to R2: {s3_key}")
        except ClientError as e:
            logger.error(f"R2 save failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"R2 save failed: {str(e)}"
            )

        url = self._key_to_url(s3_key)
        return url, s3_key

    async def get_file_path(self, s3_key: str) -> str:
        """
        For R2, this just returns the S3 key (there's no local filesystem path).
        Kept for API compatibility.
        """
        return s3_key

    async def get_file_url(self, s3_key: str) -> str:
        """Get public URL for an S3 key."""
        return self._key_to_url(s3_key)

    async def move_file(self, current_s3_key: str, new_destination: str) -> str:
        """
        Move a file in R2 (copy then delete).
        Returns the new URL.
        """
        # Extract filename from current key
        filename = current_s3_key.split('/')[-1]
        new_s3_key = f"{new_destination}/{filename}"
        
        try:
            # Copy object
            copy_source = {'Bucket': self.bucket_name, 'Key': current_s3_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=new_s3_key,
            )
            
            # Delete original
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=current_s3_key,
            )
            logger.info(f"File moved in R2: {current_s3_key} -> {new_s3_key}")
        except ClientError as e:
            logger.error(f"R2 move failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"R2 move failed: {str(e)}"
            )

        return self._key_to_url(new_s3_key)

    async def delete_file(self, s3_key: str) -> bool:
        """Delete a file from R2 by S3 key."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            logger.info(f"File deleted from R2: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"R2 delete failed: {e}")
            return False

    async def delete_file_by_url(self, url: str) -> bool:
        """
        Delete a file by its public URL.
        Extracts the S3 key from the URL and deletes it.
        """
        try:
            # Extract S3 key by removing the public URL base
            if self.public_url_base and url.startswith(self.public_url_base):
                s3_key = url[len(self.public_url_base):].lstrip('/')
            else:
                # Fallback: try to extract anything after bucket name
                # URL format: https://bucket.domain.com/path/to/file
                # or https://domain.com/path/to/file
                parts = url.split('/')
                # Assume last parts after domain are the key
                s3_key = '/'.join(parts[3:]) if len(parts) > 3 else None
            
            if not s3_key:
                logger.error(f"Cannot extract S3 key from URL: {url}")
                return False

            return await self.delete_file(s3_key)
        except Exception as e:
            logger.error(f"Error deleting by URL '{url}': {e}")
            return False

    async def get_file_for_processing(self, s3_key: str) -> str:
        """
        For document processing: download file from R2 to temp location.
        Returns the local filesystem path to the temp file.
        
        The caller is responsible for cleaning up the temp file when done.
        Use with context manager for safety:
            async with storage_service.temp_file_context(s3_key) as local_path:
                # process file at local_path
        """
        try:
            filename = s3_key.split('/')[-1]
            temp_dir = Path(tempfile.gettempdir()) / "ai_lawyer_r2"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / filename
            
            logger.info(f"Downloading {s3_key} from R2 to {temp_file}")
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                str(temp_file)
            )
            
            return str(temp_file)
        except ClientError as e:
            logger.error(f"Failed to download {s3_key} from R2: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file: {str(e)}"
            )

    @contextmanager
    def temp_file_context(self, s3_key: str):
        """
        Context manager for safely downloading and cleaning up temp files.
        
        Usage:
            with storage_service.temp_file_context(s3_key) as local_path:
                # process file at local_path
        """
        import asyncio
        
        # Get temp file path (sync wrapper for async method)
        try:
            # Run async method in thread pool since this is a context manager
            loop = asyncio.get_event_loop()
            temp_path = loop.run_until_complete(self.get_file_for_processing(s3_key))
        except Exception as e:
            logger.error(f"Failed to get temp file for {s3_key}: {e}")
            raise
        
        try:
            yield temp_path
        finally:
            # Cleanup
            try:
                if Path(temp_path).exists():
                    Path(temp_path).unlink()
                    logger.info(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _key_to_url(self, s3_key: str) -> str:
        """Convert S3 key to public URL."""
        if self.public_url_base:
            return f"{self.public_url_base}/{s3_key}"
        else:
            # Fallback: construct from bucket and endpoint
            # Format: https://bucket-name.r2.cloudflarestorage.com/path
            return f"https://{self.bucket_name}.r2.cloudflarestorage.com/{s3_key}"


# Singleton instance
r2_storage_service = None

def get_r2_storage_service():
    """Get or create R2 storage service singleton."""
    global r2_storage_service
    if r2_storage_service is None:
        r2_storage_service = R2StorageService()
    return r2_storage_service
