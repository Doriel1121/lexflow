from typing import List
import os
import google.generativeai as genai

class LLMService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            # Use gemini-2.5-flash for best performance with Pro subscription
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None
    
    async def summarize_text(self, text: str, length: str = "medium") -> str:
        try:
            if not self.model:
                return f"Summary: {text[:300]}..."
            response = self.model.generate_content(f"Summarize this legal document concisely:\n\n{text[:4000]}")
            return response.text
        except:
            return f"Summary: {text[:300]}... [AI unavailable]"

    async def generate_embedding(self, text: str) -> List[float]:
        try:
            if not self.model:
                return [0.0] * 768
            # Use the dedicated embedding model
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * 768

    async def extract_key_dates(self, text: str) -> List[str]:
        try:
            if not self.model:
                return []
            response = self.model.generate_content(f"Extract all dates from this text in YYYY-MM-DD format, return as comma-separated list:\n\n{text[:2000]}")
            return [d.strip() for d in response.text.split(",") if d.strip()]
        except:
            return []

    async def extract_parties(self, text: str) -> List[str]:
        try:
            if not self.model:
                return []
            response = self.model.generate_content(f"Extract all party names (people, companies) from this legal text, return as comma-separated list:\n\n{text[:2000]}")
            return [p.strip() for p in response.text.split(",") if p.strip()]
        except:
            return []

    async def suggest_missing_documents(self, case_context: str) -> str:
        try:
            if not self.model:
                return "AI suggestions unavailable"
            response = self.model.generate_content(f"Based on this case, suggest what documents might be missing:\n\n{case_context[:2000]}")
            return response.text
        except:
            return "AI suggestions unavailable"

llm_service = LLMService()
