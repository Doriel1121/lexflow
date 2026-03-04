from .base import OCRService
from typing import Dict, Any

class DummyOCRService(OCRService):
    async def extract_text(self, image_data: bytes) -> Dict[str, Any]:
        """
        Dummy implementation of OCR service.
        Returns a mock dictionary of extracted text and metadata.
        """
        print(f"Dummy OCR: Processing image data of length {len(image_data)} bytes.")
        return {
            "extracted_text": "This is dummy OCR extracted text for a legal document.",
            "language": "en",
            "confidence": 0.85,
            "metadata": {"dummy_field": "dummy_value"}
        }
