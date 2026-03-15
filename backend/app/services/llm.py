from typing import List
import os
from app.core.ai_provider import get_ai_provider

class LLMService:
    def __init__(self):
        self.provider = get_ai_provider()
    
    async def summarize_text(self, text: str, length: str = "medium") -> str:
        try:
            if not self.provider.active:
                return f"Summary: {text[:300]}..."
            response_text = await self.provider.generate_text(f"Summarize this legal document concisely:\n\n{text[:4000]}")
            return response_text if response_text else f"Summary: {text[:300]}... [AI unavailable]"
        except:
            return f"Summary: {text[:300]}... [AI error]"

    async def generate_embedding(self, text: str) -> List[float]:
        try:
            if not self.provider.active:
                dim = getattr(self.provider, "embedding_dimension", 768)
                return [0.0] * dim
            return await self.provider.generate_embedding(text)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            dim = getattr(self.provider, "embedding_dimension", 768)
            return [0.0] * dim

    async def extract_key_dates(self, text: str) -> List[str]:
        try:
            if not self.provider.active:
                return []
            response_text = await self.provider.generate_text(f"Extract all dates from this text in YYYY-MM-DD format, return as comma-separated list:\n\n{text[:2000]}")
            if not response_text:
                return []
            return [d.strip() for d in response_text.split(",") if d.strip()]
        except:
            return []

    async def extract_parties(self, text: str) -> List[str]:
        try:
            if not self.provider.active:
                return []
            response_text = await self.provider.generate_text(f"Extract all party names (people, companies) from this legal text, return as comma-separated list:\n\n{text[:2000]}")
            if not response_text:
                return []
            return [p.strip() for p in response_text.split(",") if p.strip()]
        except:
            return []

    async def suggest_missing_documents(self, case_context: str) -> str:
        try:
            if not self.provider.active:
                return "AI suggestions unavailable"
            response_text = await self.provider.generate_text(f"Based on this case, suggest what documents might be missing:\n\n{case_context[:2000]}")
            return response_text if response_text else "AI suggestions unavailable"
        except:
            return "AI suggestions unavailable"

llm_service = LLMService()
