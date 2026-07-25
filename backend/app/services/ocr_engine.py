import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any
import pytesseract
from app.core.config import settings
from pdf2image import convert_from_path, pdfinfo_from_path

logger = logging.getLogger(__name__)

class TesseractOCRService:
    def __init__(self):
        pass

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        try:
            info = pdfinfo_from_path(pdf_path)
            return int(info.get("Pages") or 0)
        except Exception as e:
            logger.error("Failed to inspect PDF page count: %s", e)
            return 0

    def _render_pdf_page(self, pdf_path: str, page_number: int):
        try:
            pages = convert_from_path(
                pdf_path,
                dpi=int(settings.OCR_DPI or 200),
                first_page=page_number,
                last_page=page_number,
                thread_count=1,
            )
            return pages[0] if pages else None
        except Exception as e:
            logger.error("Failed to render PDF page %s for OCR: %s", page_number, e)
            return None

    async def extract_text_from_scanned_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Memory-safe approach to extract text from a scanned PDF.
        Processes pages one by one and appends the result to a temporary file
        before returning the full string.
        
        For R2 storage: Automatically downloads file to temp location before processing.
        """
        from app.services.file_processor import FileProcessor
        
        # If using cloud storage, download file to temp location first
        actual_file_path = await FileProcessor.get_processing_file_path_async(file_path)
        is_temp_r2_file = (actual_file_path != file_path)
        
        try:
            path = Path(actual_file_path)
            if not path.exists():
                return {"text": "", "language": "en", "page_count": 0}

            dpi = int(settings.OCR_DPI or 200)
            languages = settings.TESSERACT_LANGUAGES or "heb+eng"
            logger.info(
                "Starting Tesseract OCR engine for scanned file: %s (dpi=%s, lang=%s)",
                path.name,
                dpi,
                languages,
            )

            page_count = self._get_pdf_page_count(str(path))
            if page_count == 0:
                return {"text": "Could not read pages from scanned document.", "language": "en", "page_count": 0}

            aggregated_text = []

            # Render and OCR one page at a time to avoid Render/free-tier memory spikes.
            for page_number in range(1, page_count + 1):
                logger.info("Running OCR on page %s/%s...", page_number, page_count)
                page_image = self._render_pdf_page(str(path), page_number)
                if page_image is None:
                    aggregated_text.append("")
                    continue
                page_text = pytesseract.image_to_string(page_image, lang=languages)
                aggregated_text.append(page_text)

                # Explicitly release the rendered page before moving to the next one.
                try:
                    page_image.close()
                except Exception:
                    pass
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
