from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMService(ABC):
    @abstractmethod
    async def summarize_text(self, text: str, max_length: int = 150) -> str:
        """
        Abstract method to summarize a given text.
        :param text: The input text to summarize.
        :param max_length: The maximum length of the summary.
        :return: The summarized text.
        """
        pass

    @abstractmethod
    async def extract_entities(self, text: str, entity_types: List[str] = None) -> Dict[str, List[str]]:
        """
        Abstract method to extract entities (e.g., persons, organizations, dates) from text.
        :param text: The input text.
        :param entity_types: Optional list of entity types to extract.
        :return: A dictionary where keys are entity types and values are lists of extracted entities.
        """
        pass

    @abstractmethod
    async def generate_embeddings(self, text: str) -> List[float]:
        """
        Abstract method to generate vector embeddings for a given text.
        :param text: The input text.
        :return: A list of floats representing the embedding vector.
        """
        pass
