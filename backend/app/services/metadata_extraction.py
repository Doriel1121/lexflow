import re
from typing import List, Dict
from datetime import datetime

class MetadataExtractionService:
    def __init__(self):
        # Date patterns for English and Hebrew formats
        self.date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or DD-MM-YYYY
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY-MM-DD
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',  # Month DD, YYYY
            r'\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b',  # DD Month YYYY
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
            metadata = {
                "dates": await self._extract_dates(text),
                "entities": await self._extract_entities(text, language),
                "amounts": await self._extract_amounts(text),
                "case_numbers": await self._extract_case_numbers(text),
                "routing_ids": await self._extract_routing_ids(text),
                "routing_projects": await self._extract_routing_projects(text),
                "routing_organizations": await self._extract_routing_organizations(text),
            }
            return metadata
        except Exception as e:
            # Error tolerant - return empty metadata on failure
            return {"dates": [], "entities": [], "amounts": [], "case_numbers": [], "routing_ids": [], "routing_projects": [], "routing_organizations": []}

    async def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from text."""
        dates = []
        try:
            for pattern in self.date_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                dates.extend(matches)
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
            
            # Hebrew name pattern (basic)
            if language == "he":
                hebrew_pattern = r'[\u0590-\u05FF]+\s[\u0590-\u05FF]+'
                hebrew_matches = re.findall(hebrew_pattern, text)
                entities.extend(hebrew_matches)
            
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
