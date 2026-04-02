"""
AWS S3 Storage Service
Drop-in replacement for B2/R2 — switch by setting STORAGE_BACKEND=s3 in env.
Uses the same boto3 interface already used by B2/R2.
"""
from typing import Tuple
from fastapi import UploadFile, HTTPException
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging
import tempfile
from contextlib import contextmanager

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class S3StorageService:
    """
    AWS S3 storage service.
    Identical interface to B2StorageService / R2StorageService.
    To migrate from B2: set STORAGE_BACKEND=s3 and provide S3_* env vars.
    """

    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.S3_REGION

        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )
        logger.info(f"S3StorageService initialized: bucket={self.bucket_name} region={self.region}")

    async def upload_file(self, file: UploadFile, destination_path: str) -> Tuple[str, str]:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="File type not allowed")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

        s3_key = f"{destination_path}/{file.filename}"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=file.content_type or 'application/octet-stream',
            )
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

        return self._key_to_url(s3_key), s3_key

    async def save_file_bytes(self, content: bytes, destination: str, filename: str) -> Tuple[str, str]:
        s3_key = f"{destination}/{filename}"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=s3_key,
                Body=content, ContentType='application/octet-stream',
            )
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"S3 save failed: {e}")
        return self._key_to_url(s3_key), s3_key

    async def get_file_path(self, s3_key: str) -> str:
        return s3_key

    async def get_file_url(self, s3_key: str) -> str:
        return self._key_to_url(s3_key)

    async def move_file(self, current_key: str, new_destination: str) -> str:
        filename = current_key.split('/')[-1]
        new_key = f"{new_destination}/{filename}"
        try:
            self.s3_client.copy_object(
                CopySource={'Bucket': self.bucket_name, 'Key': current_key},
                Bucket=self.bucket_name, Key=new_key,
            )
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=current_key)
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"S3 move failed: {e}")
        return self._key_to_url(new_key)

    async def delete_file(self, s3_key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete failed: {e}")
            return False

    async def delete_file_by_url(self, url: str) -> bool:
        prefix = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/"
        if url.startswith(prefix):
            return await self.delete_file(url[len(prefix):])
        logger.error(f"Cannot parse S3 URL: {url}")
        return False

    async def get_file_for_processing(self, s3_key: str) -> str:
        file_ext = Path(s3_key).suffix or ''
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        tmp.close()
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, tmp.name)
            return tmp.name
        except ClientError as e:
            Path(tmp.name).unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"S3 download failed: {e}")

    @contextmanager
    def temp_file_context(self, s3_key: str):
        import asyncio
        tmp_path = asyncio.get_event_loop().run_until_complete(
            self.get_file_for_processing(s3_key)
        )
        try:
            yield tmp_path
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _key_to_url(self, s3_key: str) -> str:
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
