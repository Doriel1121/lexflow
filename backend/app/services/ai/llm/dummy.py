from .base import LLMService
from typing import List, Dict, Any

class DummyLLMService(LLMService):
    async def summarize_text(self, text: str, max_length: int = 150) -> str:
        """
        Dummy implementation of text summarization.
        """
        print(f"Dummy LLM: Summarizing text of length {len(text)}...")
        return f"Dummy summary of the legal document. (Original length: {len(text)}, max_length: {max_length})"

    async def extract_entities(self, text: str, entity_types: List[str] = None) -> Dict[str, List[str]]:
        """
        Dummy implementation of entity extraction.
        """
        print(f"Dummy LLM: Extracting entities from text of length {len(text)}...")
        return {
            "PERSON": ["John Doe", "Jane Smith"],
            "ORGANIZATION": ["Acme Corp"],
            "DATE": ["2026-01-01"],
            "CUSTOM_LEGAL_ENTITY": ["Contract ID: 12345"]
        }

    async def generate_embeddings(self, text: str) -> List[float]:
        """
        Dummy implementation of embedding generation.
        Returns a fixed dummy embedding vector.
        """
        print(f"Dummy LLM: Generating embeddings for text of length {len(text)}...")
        # Return a fixed vector for simplicity
        return [0.1] * 768 # A common embedding dimension
