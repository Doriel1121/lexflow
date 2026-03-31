from typing import Dict, List, Any, Optional
import os
import asyncio
import logging
from app.core.config import settings
from app.core.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)

class DocumentIntelligenceService:
    def __init__(self):
        self.provider = get_ai_provider()
    
    def _language_instruction(self, language: Optional[str], text: str) -> str:
        lang = (language or "").lower()
        if lang.startswith("he") or any("\u0590" <= ch <= "\u05FF" for ch in text[:2000]):
            return "You MUST answer in Hebrew."
        if lang.startswith("ar"):
            return "You MUST answer in Arabic."
        if lang.startswith("ru"):
            return "You MUST answer in Russian."
        if lang.startswith("es"):
            return "You MUST answer in Spanish."
        if lang.startswith("fr"):
            return "You MUST answer in French."
        return "You MUST answer in the same language as the document."

    async def analyze_legal_document(self, text: str, filename: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive legal document analysis extracting all critical information
        """
        if not self.provider.active:
            return self._fallback_analysis(text, filename)
        lang_hint = self._language_instruction(language, text)
        prompt = f"""Analyze this legal document and extract ALL relevant information in JSON format.

Document: {filename}
Content: {text}

Language requirement: {lang_hint}

Extract and return ONLY valid JSON with this exact structure:
{{
  "document_type": "string (e.g., Contract, NDA, Complaint, Motion, Lease, etc.)",
  "document_subtype": "string (specific type like Employment Agreement, Purchase Agreement)",
  "jurisdiction": "string (court, state, or country)",
  "parties": [
    {{"name": "string", "role": "string (e.g., Plaintiff, Defendant, Buyer, Seller)", "id_number": "string or null (ID, passport, tax ID)", "contact": "string or null"}}
  ],
  "attorneys": [
    {{"name": "string", "firm": "string", "representing": "string", "bar_number": "string or null"}}
  ],
  "key_dates": [
    {{
      "date": "YYYY-MM-DD", 
      "description": "string (the semantic reason for this date, e.g., 'Last day to file response to motion')", 
      "type": "string (hearing, filing, response, appeal, statute_of_limitations, other)",
      "is_critical_deadline": "boolean (true if this is a date a lawyer must not miss)"
    }}
  ],
  "financial_terms": [
    {{"amount": "string", "currency": "string", "description": "string (what this amount represents)", "payer": "string or null", "payee": "string or null"}}
  ],
  "case_numbers": ["string"],
  "obligations": [
    {{"party": "string", "obligation": "string", "deadline": "string or null"}}
  ],
  "key_clauses": [
    {{"type": "string (e.g., arbitration, jurisdiction, termination)", "summary": "string"}}
  ],
  "risks": ["string"],
  "missing_items": ["string"],
  "related_documents": ["string"],
  "summary": "string (2-3 sentence executive summary)",
  "tags": ["string (relevant tags for categorization)"]
}}

IMPORTANT:
- For parties: Extract full names, roles, and ANY identification numbers (ID, passport, tax ID, company registration)
- For financial_terms: ALWAYS include description of what the amount represents (e.g., "Purchase price", "Monthly rent", "Penalty fee")
- For financial_terms: Include who pays (payer) and who receives (payee) if mentioned
- Be thorough and extract ALL information found. If a field has no data, use empty array [] or empty string "" or null.
Return ONLY the JSON, no other text."""
        try:
            result = await asyncio.wait_for(
                self.provider.generate_json(prompt),
                timeout=float(settings.AI_ANALYSIS_TIMEOUT_SECONDS or 120),
            )
        except asyncio.TimeoutError:
            logger.error("AI analysis timed out for document '%s'. Falling back.", filename)
            return self._fallback_analysis(text, filename)
        except Exception as e:
            logger.error("AI analysis error for document '%s': %s. Falling back.", filename, e)
            return self._fallback_analysis(text, filename)

        if not result:
            # If it's literally empty, use fallback
            return self._fallback_analysis(text, filename)
        
        # Ensure result is a dict (json.loads can return a string if JSON is a plain string)
        if not isinstance(result, dict):
            logger.warning(
                "AI analyze_legal_document returned non-dict type %s. Using fallback.",
                type(result).__name__,
            )
            return self._fallback_analysis(text, filename)
        
        return result
    
    def _fallback_analysis(self, text: str, filename: str) -> Dict[str, Any]:
        """Fallback when AI is unavailable"""
        return {
            "document_type": "Unknown",
            "document_subtype": "",
            "jurisdiction": "",
            "parties": [],
            "attorneys": [],
            "key_dates": [],
            "financial_terms": [],
            "case_numbers": [],
            "obligations": [],
            "key_clauses": [],
            "risks": [],
            "missing_items": [],
            "related_documents": [],
            "summary": f"Document: {filename} ({len(text)} characters)",
            "tags": ["unprocessed"]
        }

document_intelligence_service = DocumentIntelligenceService()
