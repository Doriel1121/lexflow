from typing import Optional
import os
from pathlib import Path

class OCRService:
    def __init__(self):
        pass
    
    async def extract_text_from_file(self, file_path: str) -> dict:
        """Extract text from file with metadata"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {"text": f"File: {path.name} uploaded successfully.", "language": "en", "page_count": 0}
            
            # Text files
            if path.suffix.lower() in ['.txt', '.md', '.csv', '.log']:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        text = f.read()
                        return {"text": text, "language": "en", "page_count": 1}
                except:
                    pass
            
            # PDF files
            if path.suffix.lower() == '.pdf':
                try:
                    import PyPDF2
                    text = ""
                    page_count = 0
                    with open(path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        page_count = len(reader.pages)
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                    
                    # Hybrid Routing Logic
                    # If this is a digital PDF, text length will be substantial. 
                    # If it's a scanned PDF, PyPDF2 extracts virtually nothing (or just noise).
                    # We expect at least ~100 characters per page for a real digital document.
                    text_length = len(text.strip())
                    threshold = max(200, page_count * 100)
                    
                    if text_length < threshold:
                        from app.services.ocr_engine import tesseract_ocr_service
                        return await tesseract_ocr_service.extract_text_from_scanned_pdf(file_path)
                    
                    return {"text": text, "language": "en", "page_count": page_count}
                except Exception as e:
                    # If PyPDF2 crashes entirely (corrupted metadata etc), fallback to OCR
                    from app.services.ocr_engine import tesseract_ocr_service
                    return await tesseract_ocr_service.extract_text_from_scanned_pdf(file_path)
            
            # Other files
            return {"text": f"Document: {path.name}\n\nFile Type: {path.suffix}\nSize: {path.stat().st_size} bytes", "language": "en", "page_count": 1}
        except Exception as e:
            return {"text": f"Document uploaded: {path.name if 'path' in locals() else 'file'}", "language": "en", "page_count": 0}
    
    async def extract_text(self, file_path: str, language: Optional[str] = None) -> dict:
        return await self.extract_text_from_file(file_path)

    async def detect_language(self, file_path: str) -> str:
        return "en"

ocr_service = OCRService()
