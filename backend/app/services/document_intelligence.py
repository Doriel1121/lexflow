from typing import Dict, List, Any
import os
from app.core.ai_provider import get_ai_provider

class DocumentIntelligenceService:
    def __init__(self):
        self.provider = get_ai_provider()
    
    async def analyze_legal_document(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Comprehensive legal document analysis extracting all critical information
        """
        if not self.provider.active:
            return self._fallback_analysis(text, filename)
        prompt = f"""Analyze this legal document and extract ALL relevant information in JSON format.

Document: {filename}
Content: {text}

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
        result = await self.provider.generate_json(prompt)
        if not result:
            # If it's literally empty, use fallback
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
