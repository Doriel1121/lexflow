import logging
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case
from app.services.case_suggestion import case_suggestion_service

logger = logging.getLogger(__name__)


class SmartRouter:
    async def route_document(
        self,
        db: AsyncSession,
        content: str,
        metadata: Dict = None,
    ) -> Optional[Case]:
        """
        Auto-assign only on high-confidence case ID match (product policy).
        Medium/low suggestions are handled in the Intake UI.
        """
        metadata = metadata or {}
        suggestion = await case_suggestion_service.suggest_case(
            db,
            search_text=content,
            org_id=metadata.get("organization_id"),
        )
        if suggestion and suggestion.confidence == "high":
            case = await db.get(Case, suggestion.case_id)
            if case:
                logger.info(
                    "Rule-based/high-confidence route: Case %s (%s)",
                    case.id,
                    suggestion.reason,
                )
                return case

        logger.info("No high-confidence automatic route found.")
        return None


smart_router = SmartRouter()
