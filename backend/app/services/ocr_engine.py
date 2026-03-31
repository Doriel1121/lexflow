import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any
import pytesseract
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

class TesseractOCRService:
    def __init__(self):
        pass

    def _extract_pages_from_pdf(self, pdf_path: str) -> list:
        # Convert PDF into a list of PIL Images (one per page)
        try:
            return convert_from_path(pdf_path, dpi=300)
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            return []

    async def extract_text_from_scanned_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Memory-safe approach to extract text from a scanned PDF.
        Processes pages one by one and appends the result to a temporary file
        before returning the full string.
        
        For R2 storage: Automatically downloads file to temp location before processing.
        """
        from app.services.file_processor import FileProcessor
        
        # If using R2, download file to temp location first
        actual_file_path = FileProcessor.get_processing_file_path(file_path)
        is_temp_r2_file = (actual_file_path != file_path)
        
        try:
            path = Path(actual_file_path)
            if not path.exists():
                return {"text": "", "language": "en", "page_count": 0}

            logger.info(f"Starting Tesseract OCR engine for scanned file: {path.name}")
            
            pages = self._extract_pages_from_pdf(str(path))
            page_count = len(pages)
            
            if page_count == 0:
                return {"text": "Could not read pages from scanned document.", "language": "en", "page_count": 0}

            aggregated_text = []

            # Iterate page by page
            for i, page_image in enumerate(pages):
                logger.info(f"Running OCR on page {i+1}/{page_count}...")
                # Run pytesseract with Hebrew + English support
                page_text = pytesseract.image_to_string(page_image, lang='heb+eng')
                aggregated_text.append(page_text)
                
                # Explicitly delete the image to free up RAM
                del page_image 

            full_text = "\n\n--- Page Break ---\n\n".join(aggregated_text)
            
            logger.info(f"OCR Complete for {path.name}. Extracted {len(full_text)} characters.")
            return {
                "text": full_text,
                "language": "en",
                "page_count": page_count
            }
        finally:
            # Clean up R2 temp file if downloaded
            if is_temp_r2_file:
                FileProcessor.cleanup_temp_file(actual_file_path)

tesseract_ocr_service = TesseractOCRService()
