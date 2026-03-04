from typing import Dict, List, Any
import google.generativeai as genai
import os
import json

class DocumentIntelligenceService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None
    
    async def analyze_legal_document(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Comprehensive legal document analysis extracting all critical information
        """
        if not self.model:
            return self._fallback_analysis(text, filename)
        
        try:
            prompt = f"""Analyze this legal document and extract ALL relevant information in JSON format.

Document: {filename}
Content: {text[:8000]}

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
    {{"date": "YYYY-MM-DD", "description": "string", "type": "string (deadline, execution, expiration)"}}
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

            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Clean up markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result = json.loads(result_text.strip())
            return result
            
        except Exception as e:
            print(f"AI analysis error: {e}")
            return self._fallback_analysis(text, filename)
    
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
