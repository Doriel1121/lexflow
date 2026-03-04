from typing import Optional
from fastapi import UploadFile, HTTPException
import os
import aiofiles
from pathlib import Path
import shutil

class StorageService:
    def __init__(self):
        # Use relative path that works cross-platform
        base_dir = Path(__file__).parent.parent.parent.parent
        self.upload_dir = base_dir / "backend" / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create standard folder structure
        self._create_folder_structure()
    
    def _create_folder_structure(self):
        """Create standard folder hierarchy for documents"""
        folders = [
            "inbox/unprocessed",
            "inbox/processed",
            "temp",
        ]
        for folder in folders:
            (self.upload_dir / folder).mkdir(parents=True, exist_ok=True)
    
    def _get_case_folder(self, case_id: int, subfolder: str = "documents") -> Path:
        """Get the folder path for a specific case"""
        case_folder = self.upload_dir / f"cases/{case_id}" / subfolder
        case_folder.mkdir(parents=True, exist_ok=True)
        return case_folder
    
    async def save_file_bytes(self, content: bytes, destination: str, filename: str) -> tuple[str, str]:
        """Save raw bytes to storage"""
        file_path = self.upload_dir / destination / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # Return both the relative path and full URL
        relative_path = f"{destination}/{filename}"
        url = f"http://localhost:8000/uploads/{relative_path}"
        return str(file_path), url
    
    async def upload_file(self, file: UploadFile, destination_path: str) -> str:
        """Save uploaded file to storage"""
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file extension
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file_ext} not allowed. Allowed: {', '.join(allowed_extensions)}"
            )
        
        file_path = self.upload_dir / destination_path / file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read and save file
        content = await file.read()
        
        # Check file size (20MB limit)
        max_size = 20 * 1024 * 1024  # 20MB
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="File too large (max 20MB)")
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return f"http://localhost:8000/uploads/{destination_path}/{file.filename}"

    async def move_file(self, current_path: str, new_destination: str) -> str:
        """Move file from one location to another"""
        source = self.upload_dir / current_path
        dest_dir = self.upload_dir / new_destination
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        dest = dest_dir / source.name
        shutil.move(str(source), str(dest))
        
        return f"http://localhost:8000/uploads/{new_destination}/{source.name}"

    async def get_file_url(self, file_path: str) -> str:
        """Get URL for a file path"""
        return f"http://localhost:8000/uploads/{file_path}"
    
    async def get_file_path(self, relative_path: str) -> Path:
        """Get full file system path from relative path"""
        return self.upload_dir / relative_path

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage"""
        try:
            full_path = self.upload_dir / file_path
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False

storage_service = StorageService()
