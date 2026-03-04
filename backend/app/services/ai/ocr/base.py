from abc import ABC, abstractmethod
from typing import Dict, Any

class OCRService(ABC):
    @abstractmethod
    async def extract_text(self, image_data: bytes) -> Dict[str, Any]:
        """
        Abstract method to extract text and other relevant information from an image.
        :param image_data: The image content as bytes.
        :return: A dictionary containing extracted text and potentially other metadata.
        """
        pass
