from typing import List, Dict
import os
import json
from datetime import datetime, timedelta
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

    async def extract_key_dates(self, text: str) -> List[Dict[str, str]]:
        """Extract UPCOMING legal deadlines only, excluding citations and irrelevant dates."""
        try:
            if not self.provider.active:
                return []
            
            today = datetime.now()
            three_years_ago = (today - timedelta(days=3*365)).strftime("%Y-%m-%d")
            ten_years_future = (today + timedelta(days=10*365)).strftime("%Y-%m-%d")
            
            prompt = (
                "You are a legal document analyzer. Extract UPCOMING LEGAL DEADLINES only.\n\n"
                "CRITICAL RULES:\n"
                "1. Extract ONLY future/upcoming deadlines relevant to the case (filing deadlines, hearing dates, response dates, appeal deadlines)\n"
                "2. IGNORE and EXCLUDE:\n"
                f"   - Case law citations and legal references\n"
                f"   - Historical dates from past cases (dates before {three_years_ago})\n"
                f"   - Years that don't make sense ({today.year} +/- 10 years is valid range)\n"
                f"   - Dates way in the future (after {ten_years_future})\n"
                "   - Dates mentioned just as examples or in quoted text\n"
                "3. For each deadline: DATE (YYYY-MM-DD), TYPE (hearing/filing/response/appeal/statute_of_limitations/other), DESCRIPTION\n"
                "4. Be skeptical - ONLY include dates that are clearly ACTION DATES for THIS case\n"
                "5. Return ONLY valid deadlines within realistic range\n\n"
                "Document text:\n"
                f"{text[:3000]}\n\n"
                'Format: Return ONLY JSON array - [{"date": "YYYY-MM-DD", "type": "filing", "description": "context"}]\n\n'
                "If no valid deadlines, return []"
            )
            
            response_text = await self.provider.generate_text(prompt)
            if not response_text:
                return []
            
            try:
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                
                deadlines = json.loads(response_text)
                validated = [d for d in deadlines if self._is_valid_deadline(d.get("date"))]
                return validated
            except json.JSONDecodeError:
                return []
        except:
            return []

    def _is_valid_deadline(self, date_str: str) -> bool:
        """Check if date is within realistic legal deadline range."""
        try:
            if not date_str:
                return False
            d_date = datetime.fromisoformat(date_str.split("T")[0])
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            ten_years_future = today + timedelta(days=10*365)
            return three_years_ago <= d_date <= ten_years_future
        except:
            return False

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
