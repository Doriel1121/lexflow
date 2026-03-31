"""
Document Processing Helpers for B2/R2 Integration

Provides utilities for safely handling file access during document processing
whether files are stored locally or in Backblaze B2/Cloudflare R2.
"""
from pathlib import Path
import tempfile
import logging
import asyncio
from app.core.config import settings
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

class FileProcessor:
    """Helper class for safely handling files during document processing."""
    
    @staticmethod
    async def get_processing_file_path_async(file_path: str) -> str:
        """
        Async version: Get the actual filesystem path for processing.
        Use this when you're already in an async context (recommended).
        
        For local storage: returns file_path as-is.
        For B2/R2: downloads file to temp location and returns temp path.
        """
        # Check if it's a local storage path (actual filesystem path)
        if Path(file_path).exists():
            logger.info(f"Using local file: {file_path}")
            return file_path
        
        # Not a local path - try to download from cloud storage (B2/R2)
        if not (settings.B2_ENABLED or settings.R2_ENABLED):
            logger.warning(f"File path does not exist and cloud storage not enabled: {file_path}")
            return file_path
        
        try:
            logger.info(f"Downloading cloud file for processing: {file_path}")
            temp_path = await storage_service.get_file_for_processing(file_path)
            logger.info(f"Successfully downloaded {file_path} to temp: {temp_path}")
            
            # Verify the temp file was actually created
            if not Path(temp_path).exists():
                logger.error(f"Temp file does not exist after download: {temp_path}")
                return file_path
                
            return temp_path
        except Exception as e:
            logger.error(f"Failed to download cloud file {file_path}: {type(e).__name__}: {e}", exc_info=True)
            # Return original file_path anyway - OCR will handle the error gracefully
            return file_path
    
    @staticmethod
    def cleanup_temp_file(file_path: str) -> None:
        """Clean up temp file if it was downloaded from R2."""
        if not settings.R2_ENABLED:
            return
        
        temp_dir = Path(tempfile.gettempdir()) / "ai_lawyer_r2"
        file_path_obj = Path(file_path)
        
        # Only delete if it's in our temp directory
        try:
            if file_path_obj.parent == temp_dir and file_path_obj.exists():
                file_path_obj.unlink()
                logger.info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
