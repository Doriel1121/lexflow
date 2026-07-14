import re
from typing import List, Dict, Any
from datetime import datetime


def _normalize_ocr_whitespace(text: str) -> str:
    """Collapse OCR line breaks within Hebrew/English words into spaces.

    Many Hebrew PDFs produce text like 'חברת\nמגדלי\nהעתיד\nבע"מ' where
    newlines appear between words that should be on one line.
    """
    # Collapse any sequence of whitespace (including newlines) into a single space
    return re.sub(r"\s+", " ", text).strip()


class MetadataExtractionService:
    def __init__(self):
        # Date patterns for English and Hebrew formats
        self.date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or DD-MM-YYYY
            r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',  # DD.MM.YYYY
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY-MM-DD
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',  # Month DD, YYYY
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th),? \d{4}\b',  # Month 1st, YYYY
            r'\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b',  # DD Month YYYY
            r'\b\d{1,2}(?:st|nd|rd|th) (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b',  # 1st Month YYYY
        ]
        
        # Case number patterns
        self.case_patterns = [
            r'\b(?:Case|File|Matter|Docket)[\s#:]*[A-Z0-9-]+\b',
            r'\b[A-Z]{2,4}[-/]?\d{4,6}[-/]?\d{0,4}\b',  # CV-2024-1234
            r'\b\d{2,4}[-/]\d{4,6}\b',  # 24-12345
        ]
        
        # Collection Routing patterns (IDs, Registration Numbers, Projects)
        self.routing_id_patterns = [
            r'\b(?:ID|ID No|Passport|Registration|Company No)[\s:#.]+(\d{8,12})\b',
            r'\b\d{9}\b' # Standard Israeli ID format
        ]
        
        self.routing_project_patterns = [
            r'\b(?:Project|Site|Venture)[\s:]+([A-Z][a-zA-Z\s0-9]{3,25})\b',
            r'\b(?:Matter of|Re:)[\s]+([A-Z][a-zA-Z\s0-9]{3,30})\b'
        ]
        
        # Organization / Company patterns (English + Hebrew)
        self.routing_organization_patterns = [
            r'\b([A-Z][a-zA-Z\s&]{2,40}(?:Inc|LLC|Ltd|Corp|LLP|LP|Co|PLC|GmbH))\b',
            r'\b([\u0590-\u05FF][\u0590-\u05FF\s]{2,30}(?:בע"מ|ב\.מ\.|בעמ))\b',
        ]
        
        # Amount patterns
        self.amount_patterns = [
            r'\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # $1,000.00
            r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?(?:USD|EUR|ILS|NIS|₪)\b',  # 1000 USD
            r'₪\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # ₪1,000.00
        ]
        
        # Entity patterns (names, organizations)
        self.entity_patterns = [
            r'\b[A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b',  # John Doe, John Q. Public
            r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+ (?:Inc|LLC|Ltd|Corp|Co|LLP|LP)\b',  # Company Inc
        ]

    async def extract_metadata(self, text: str, language: str = "en") -> Dict[str, List[str]]:
        """Extract metadata from text with error tolerance."""
        try:
            # Pre-normalize OCR whitespace for better regex matching
            normalized_text = _normalize_ocr_whitespace(text)
            metadata = {
                "dates": await self._extract_dates(normalized_text),
                "entities": await self._extract_entities(normalized_text, language),
                "amounts": await self._extract_amounts(normalized_text),
                "case_numbers": await self._extract_case_numbers(normalized_text),
                "routing_ids": await self._extract_routing_ids(normalized_text),
                "routing_projects": await self._extract_routing_projects(normalized_text),
                "routing_organizations": await self._extract_routing_organizations(normalized_text),
            }
            return metadata
        except Exception as e:
            # Error tolerant - return empty metadata on failure
            return {"dates": [], "entities": [], "amounts": [], "case_numbers": [], "routing_ids": [], "routing_projects": [], "routing_organizations": []}

    def classify_document(self, text: str, filename: str = "") -> str:
        """Fast rule-based classification used when the LLM is slow or vague."""
        haystack = f"{filename}\n{text or ''}".lower()
        rules = [
            ("Statement of Claim", ["statement of claim", "complaint", "plaintiff", "defendant"]),
            ("Motion", ["motion", "application", "petition", "בקשה"]),
            ("Court Decision", ["decision", "order", "judgment", "ruling", "פסק דין", "החלטה"]),
            ("Contract", ["agreement", "contract", "terms and conditions", "הסכם", "חוזה"]),
            ("Invoice", ["invoice", "tax invoice", "amount due", "חשבונית"]),
            ("Legal Correspondence", ["dear counsel", "correspondence", "please review", "response deadline", "re:"]),
            ("Power of Attorney", ["power of attorney", "ייפוי כוח"]),
            ("Affidavit", ["affidavit", "sworn", "תצהיר"]),
        ]
        for label, needles in rules:
            if any(needle in haystack for needle in needles):
                return label

        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix in {"jpg", "jpeg", "png", "tif", "tiff"}:
            return "Scanned Image"
        if suffix in {"pdf", "doc", "docx"}:
            return "Legal Document"
        return "Unknown"

    def build_fast_summary(
        self,
        text: str,
        filename: str,
        *,
        classification: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Generate an immediate useful summary without another AI call."""
        parts = [classification or "Document"]

        entities = metadata.get("entities") or []
        if entities:
            parts.append("Parties: " + ", ".join(str(e) for e in entities[:3]))

        dates = metadata.get("dates") or []
        if dates:
            parts.append("Dates found: " + ", ".join(str(d) for d in dates[:3]))

        amounts = metadata.get("amounts") or []
        if amounts:
            parts.append("Amounts: " + ", ".join(str(a) for a in amounts[:3]))

        if len(parts) > 1:
            return ". ".join(parts) + "."

        clean_text = _normalize_ocr_whitespace(text or "")
        if clean_text:
            return clean_text[:280] + ("..." if len(clean_text) > 280 else "")
        return f"Document received: {filename}"

    async def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from text."""
        dates = []
        try:
            # OCR (especially for Hebrew PDFs) often introduces spaces around separators,
            # e.g. "10. 05. 2026". Normalize common numeric date separators to improve hits.
            normalized = re.sub(r"(\d)\s*([./-])\s*(\d)", r"\1\2\3", text)
            for pattern in self.date_patterns:
                matches = re.findall(pattern, normalized, re.IGNORECASE)
                dates.extend(matches)

            # Heuristic fallback: detect standalone years (helps when separators are OCR-broken).
            years = re.findall(r"\b(19\d{2}|20\d{2})\b", normalized)
            dates.extend(years)
            return list(set(dates))[:20]  # Limit to 20 unique dates
        except:
            return []

    async def _extract_entities(self, text: str, language: str) -> List[str]:
        """Extract person and organization names."""
        entities = []
        try:
            for pattern in self.entity_patterns:
                matches = re.findall(pattern, text)
                entities.extend(matches)
            
            # Hebrew name pattern: 2-4 Hebrew words (person or organization)
            # This catches names like "דוריאל אבויה" or "יוסי כהן"
            hebrew_name_pattern = r'[\u0590-\u05FF]+(?:\s+[\u0590-\u05FF]+){1,3}'
            hebrew_matches = re.findall(hebrew_name_pattern, text)
            # Filter out very short matches and common Hebrew stopwords
            hebrew_stopwords = {'של', 'על', 'את', 'עם', 'לא', 'כי', 'גם', 'או', 'אם', 'זה', 'היא', 'הוא', 'אני', 'הם'}
            for match in hebrew_matches:
                words = match.split()
                # Skip if first word is a stopword or match is too short
                if words[0] in hebrew_stopwords:
                    continue
                if len(match) >= 4:  # At least 4 chars
                    entities.append(match)
            
            return list(set(entities))[:30]  # Limit to 30 unique entities
        except:
            return []

    async def _extract_amounts(self, text: str) -> List[str]:
        """Extract monetary amounts."""
        amounts = []
        try:
            for pattern in self.amount_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                amounts.extend(matches)
            return list(set(amounts))[:15]  # Limit to 15 unique amounts
        except:
            return []

    async def _extract_case_numbers(self, text: str) -> List[str]:
        """Extract possible case numbers."""
        case_numbers = []
        try:
            for pattern in self.case_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                case_numbers.extend(matches)
            return list(set(case_numbers))[:10]  # Limit to 10 unique case numbers
        except:
            return []
            
    async def _extract_routing_ids(self, text: str) -> List[str]:
        """Extract primary IDs for intelligent collection auto-routing."""
        ids = []
        try:
            for pattern in self.routing_id_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for item in matches:
                    ids.append(item[0] if isinstance(item, tuple) else item)
            return list(set(ids))[:5]
        except:
            return []

    async def _extract_routing_projects(self, text: str) -> List[str]:
        """Extract project names for intelligent collection auto-routing."""
        projects = []
        try:
            for pattern in self.routing_project_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for item in matches:
                    projects.append(item[0] if isinstance(item, tuple) else item)
            return list(set([p.strip() for p in projects]))[:5]
        except:
            return []

    async def _extract_routing_organizations(self, text: str) -> List[str]:
        """Extract company / organization names for intelligent collection auto-routing."""
        orgs = []
        try:
            for pattern in self.routing_organization_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
                for item in matches:
                    name = (item[0] if isinstance(item, tuple) else item).strip()
                    if name:
                        orgs.append(name)
            return list(set(orgs))[:10]
        except:
            return []

metadata_extraction_service = MetadataExtractionService()
