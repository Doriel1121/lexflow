from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.case import Case
from app.db.models.client import Client
from app.services.llm import llm_service
import logging

logger = logging.getLogger(__name__)

class SmartRouter:
    async def route_document(
        self, 
        db: AsyncSession, 
        content: str, 
        metadata: Dict = None
    ) -> Optional[Case]:
        """
        Determines the appropriate case for a document based on content and metadata.
        """
        metadata = metadata or {}
        
        # 1. Rule-based matching (e.g. Case ID in subject/content)
        # Look for pattern "Case #123" or "Case-123"
        import re
        case_id_match = re.search(r"Case\s*[#\-]?\s*(\d+)", content, re.IGNORECASE)
        if case_id_match:
            case_id = int(case_id_match.group(1))
            case = await db.get(Case, case_id)
            if case:
                logger.info(f"Rule-based match: Case {case_id}")
                return case

        # 2. Client Name Matching
        # This requires Client model query. 
        # For now, we simulate looking up cases by client name if found in content.
        
        # 3. AI-based Classification (Fallback)
        # Ask LLM: "Given this text, which case does it belong to from this list...?"
        # This is expensive, so maybe we just extract keywords and search.
        
        # Simplified AI routing: Extract keywords and fuzzy match case titles
        keywords = await llm_service.extract_keywords(content)
        
        # Search cases by keywords (simulated)
        # In real implementation: use pgvector or full-text search
        
        # For MVP: Return None if no direct match found
        logger.info("No automatic route found.")
        return None

smart_router = SmartRouter()
