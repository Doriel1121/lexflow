"""
Backblaze B2 Storage Service
Provides S3-compatible interface for storing files in Backblaze B2
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


class B2StorageService:
    """
    Storage service for Backblaze B2.
    Uses boto3 (AWS SDK) to interact with B2's S3-compatible API.
    B2 is completely S3-compatible, so we use the same boto3 client.
    """
    
    def __init__(self):
        if not settings.B2_ENABLED:
            raise ValueError("B2 is not enabled. Set B2_ENABLED=true in .env")
        
        self.bucket_name = settings.B2_BUCKET_NAME
        self.endpoint_url = settings.B2_ENDPOINT_URL
        
        # Extract region code from endpoint URL
        # e.g., from "https://s3.eu-central-003.backblazeb2.com" extract "eu-central-003"
        self.region_code = self._extract_region_from_endpoint(self.endpoint_url)
        
        # Use custom domain if provided and valid, otherwise use B2 default
        url_config = settings.B2_PUBLIC_URL.strip() if settings.B2_PUBLIC_URL else ""
        # Skip if empty, whitespace-only, or contains placeholder text
        is_invalid = (not url_config or 
                     "paste" in url_config.lower() or 
                     "placeholder" in url_config.lower())
        self.public_url_base = url_config.rstrip('/') if (url_config and not is_invalid) else None
        
        # Initialize S3 client for B2 (B2 is 100% S3-compatible)
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.B2_ENDPOINT_URL,
            aws_access_key_id=settings.B2_APPLICATION_KEY_ID,
            aws_secret_access_key=settings.B2_APPLICATION_KEY,
            region_name='us-west-000',  # B2 region (required format for B2)
        )
        
        logger.info(f"B2StorageService initialized with bucket: {self.bucket_name} (region: {self.region_code})")

    # ------------------------------------------------------------------
    # Public API (matches StorageService interface)
    # ------------------------------------------------------------------

    async def upload_file(self, file: UploadFile, destination_path: str) -> Tuple[str, str]:
        """
        Save an uploaded file to B2.

        Args:
            file: FastAPI UploadFile
            destination_path: Relative path in bucket (e.g., "cases/123/documents")

        Returns:
            (url, b2_key) — url is the public URL for accessing the file;
                           b2_key is the full object path in B2
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

        # Build B2 key (full path in bucket)
        b2_key = f"{destination_path}/{file.filename}"
        
        try:
            # Upload to B2
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=b2_key,
                Body=content,
                ContentType=file.content_type or 'application/octet-stream',
            )
            logger.info(f"File uploaded to B2: {b2_key}")
        except ClientError as e:
            logger.error(f"B2 upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"B2 upload failed: {str(e)}"
            )

        # Generate public URL
        url = self._key_to_url(b2_key)
        return url, b2_key

    async def save_file_bytes(
        self, content: bytes, destination: str, filename: str
    ) -> Tuple[str, str]:
        """Save raw bytes to B2. Returns (url, b2_key)."""
        b2_key = f"{destination}/{filename}"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=b2_key,
                Body=content,
                ContentType='application/octet-stream',
            )
            logger.info(f"Bytes saved to B2: {b2_key}")
        except ClientError as e:
            logger.error(f"B2 save failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"B2 save failed: {str(e)}"
            )

        url = self._key_to_url(b2_key)
        return url, b2_key

    async def get_file_path(self, b2_key: str) -> str:
        """
        For B2, this just returns the B2 key (there's no local filesystem path).
        Kept for API compatibility.
        """
        return b2_key

    async def get_file_url(self, b2_key: str) -> str:
        """Get public URL for a B2 key."""
        return self._key_to_url(b2_key)

    async def move_file(self, current_b2_key: str, new_destination: str) -> str:
        """
        Move a file in B2 (copy then delete).
        Returns the new URL.
        """
        # Extract filename from current key
        filename = current_b2_key.split('/')[-1]
        new_b2_key = f"{new_destination}/{filename}"
        
        try:
            # Copy object
            copy_source = {'Bucket': self.bucket_name, 'Key': current_b2_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=new_b2_key,
            )
            
            # Delete original
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=current_b2_key,
            )
            logger.info(f"File moved in B2: {current_b2_key} -> {new_b2_key}")
        except ClientError as e:
            logger.error(f"B2 move failed: {e}")
            raise HTTPException(status_code=500, detail=f"B2 move failed: {str(e)}")

        return self._key_to_url(new_b2_key)

    async def delete_file(self, b2_key: str) -> bool:
        """Delete a file in B2 by its key. Returns True if deleted."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=b2_key,
            )
            logger.info(f"File deleted from B2: {b2_key}")
            return True
        except ClientError as e:
            logger.error(f"B2 delete failed: {e}")
            return False

    async def delete_file_by_url(self, url: str) -> bool:
        """
        Delete a file by its public URL.
        Parses the URL to extract the B2 key.
        """
        try:
            # Extract B2 key from URL
            # URL format: https://f000.backblazeb2.com/file/bucket-name/path/to/file
            # or: https://your-custom-domain/path/to/file
            
            if self.public_url_base:
                prefix = self.public_url_base.rstrip('/') + '/'
                if url.startswith(prefix):
                    b2_key = url[len(prefix):]
                else:
                    # Try to extract after bucket name
                    marker = f"/file/{self.bucket_name}/"
                    idx = url.find(marker)
                    if idx == -1:
                        logger.error(f"Cannot parse B2 URL: {url}")
                        return False
                    b2_key = url[idx + len(marker):]
            else:
                logger.error("B2_PUBLIC_URL not configured")
                return False

            return await self.delete_file(b2_key)
        except Exception as e:
            logger.error(f"Error deleting file by URL '{url}': {e}")
            return False

    async def get_file_for_processing(self, b2_key: str) -> str:
        """
        Download file from B2 to temp location for processing (OCR, AI analysis).
        Preserves original file extension for proper file type detection.
        Automatically cleaned up with temp_file_context.
        
        Args:
            b2_key: B2 object key (e.g., "cases/123/documents/myfile.txt")
        
        Returns:
            Path to temp file ready for processing (with original extension preserved)
        """
        # Extract original filename and extension from B2 key
        original_filename = Path(b2_key).name
        file_ext = Path(original_filename).suffix or ''
        
        # Create temp file with the original extension so OCR can detect file type
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Download file from B2 to temp location
            self.s3_client.download_file(
                Bucket=self.bucket_name,
                Key=b2_key,
                Filename=temp_path,
            )
            logger.info(f"Downloaded B2 file for processing: {b2_key} -> {temp_path} (ext: {file_ext})")
            return temp_path
        except ClientError as e:
            logger.error(f"Failed to download file from B2: {e}")
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file from B2: {str(e)}"
            )

    @contextmanager
    def temp_file_context(self, file_path: str):
        """
        Context manager for safely accessing files during processing.
        For B2: downloads to temp, cleans up after block exits.
        
        Usage:
            with storage_service.temp_file_context(b2_key) as temp_path:
                process_file(temp_path)
                # Auto-cleanup happens here
        """
        import asyncio
        temp_file_path = None
        try:
            # Get temp file path
            loop = asyncio.get_event_loop()
            temp_file_path = loop.run_until_complete(self.get_file_for_processing(file_path))
            yield temp_file_path
        finally:
            # Clean up temp file
            if temp_file_path and Path(temp_file_path).exists():
                try:
                    Path(temp_file_path).unlink()
                    logger.info(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_region_from_endpoint(self, endpoint_url: str) -> str:
        """
        Extract region code from B2 endpoint URL.
        Examples:
            https://s3.us-west-000.backblazeb2.com -> us-west-000
            https://s3.eu-central-003.backblazeb2.com -> eu-central-003
        """
        try:
            # Format: https://s3.{region}.backblazeb2.com
            parts = endpoint_url.replace("https://", "").replace("http://", "").split(".")
            if len(parts) >= 2:
                return parts[1]  # Extract the region part
        except Exception as e:
            logger.warning(f"Failed to extract region from {endpoint_url}: {e}")
        return "us-west-000"  # Fallback to US region

    def _get_file_endpoint_number(self, region_code: str) -> str:
        """
        Map B2 region code to file endpoint number.
        B2 regions and their file endpoint numbers.
        """
        # Map of region codes to file endpoint numbers
        region_to_endpoint = {
            "us-west-000": "f000",
            "eu-central-001": "f001",
            "eu-central-002": "f002", 
            "eu-central-003": "f003",
            "ap-southeast-002": "f004",
        }
        
        # Try exact match first
        if region_code in region_to_endpoint:
            return region_to_endpoint[region_code]
        
        # Try to extract numeric suffix and use it
        try:
            if "-" in region_code:
                numeric_part = region_code.split("-")[-1]
                return f"f{numeric_part}"
        except Exception as e:
            logger.warning(f"Failed to extract endpoint number from {region_code}: {e}")
        
        return "f000"  # Fallback to US endpoint

    def _key_to_url(self, b2_key: str) -> str:
        """
        Generate a presigned (authenticated) URL for the B2 file.
        Presigned URLs work for private buckets and expire after a set time.
        Valid for 7 days to allow time for OCR processing and document analysis.
        """
        try:
            # Generate a presigned URL valid for 7 days (604800 seconds)
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': b2_key},
                ExpiresIn=604800  # 7 days
            )
            logger.info(f"Generated presigned URL for {b2_key}")
            return presigned_url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            # Fallback: return a public URL (will fail if bucket is private)
            if self.public_url_base:
                return f"{self.public_url_base}/{b2_key}"
            
            endpoint_num = self._get_file_endpoint_number(self.region_code)
            return f"https://{endpoint_num}.backblazeb2.com/file/{self.bucket_name}/{b2_key}"
