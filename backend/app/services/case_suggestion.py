"""Unified case suggestion for intake, email routing, and smart router."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case, CaseStatus
from app.db.models.client import Client
from app.db.models.document import Document
from app.db.models.document_metadata import DocumentMetadata

_STOPWORDS = frozenset(
    {
        "from",
        "subject",
        "dear",
        "regards",
        "with",
        "that",
        "this",
        "have",
        "been",
        "attachment",
        "document",
    }
)


@dataclass
class CaseSuggestion:
    case_id: int
    case_title: str
    reason: str
    confidence: str  # high | medium | low

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_title": self.case_title,
            "reason": self.reason,
            "confidence": self.confidence,
        }


class CaseSuggestionService:
    async def suggest_case(
        self,
        db: AsyncSession,
        *,
        search_text: str,
        org_id: Optional[int],
        metadata: Optional[DocumentMetadata] = None,
    ) -> Optional[CaseSuggestion]:
        text = (search_text or "").lower()
        if not text.strip():
            return None

        base_query = select(Case).where(
            Case.status != CaseStatus.CLOSED,
            Case.organization_id == org_id if org_id else True,
        )

        id_match = re.search(r"case\s*[#\-]?\s*(\d+)", text, re.IGNORECASE)
        if id_match:
            cid = int(id_match.group(1))
            case = await db.get(Case, cid)
            if case and (not org_id or case.organization_id == org_id):
                return CaseSuggestion(
                    case_id=case.id,
                    case_title=case.title or f"Case #{case.id}",
                    reason=f"Case #{cid} found in subject/content",
                    confidence="high",
                )

        if metadata and metadata.entities:
            for ent in metadata.entities or []:
                name = (ent.get("name") if isinstance(ent, dict) else str(ent) or "").strip()
                if not name or len(name) < 3:
                    continue
                client_result = await db.execute(
                    select(Client).where(
                        func.lower(Client.name).contains(name.lower()),
                        Client.organization_id == org_id if org_id else True,
                    )
                )
                client = client_result.scalars().first()
                if client:
                    case_result = await db.execute(
                        base_query.where(Case.client_id == client.id).limit(1)
                    )
                    case = case_result.scalars().first()
                    if case:
                        return CaseSuggestion(
                            case_id=case.id,
                            case_title=case.title or f"Case #{case.id}",
                            reason=f"Client name match: {name}",
                            confidence="medium",
                        )

        words = [
            w
            for w in re.findall(r"\b\w{4,}\b", text)
            if w not in _STOPWORDS
        ]
        if words:
            cases_result = await db.execute(base_query.limit(100))
            cases = cases_result.scalars().all()
            best, best_count = None, 0
            for case in cases:
                title_words = set(re.findall(r"\b\w{4,}\b", (case.title or "").lower()))
                overlap = sum(1 for w in words if w in title_words)
                if overlap > best_count:
                    best, best_count = case, overlap
            if best and best_count >= 2:
                return CaseSuggestion(
                    case_id=best.id,
                    case_title=best.title or f"Case #{best.id}",
                    reason=f"Keyword match ({best_count} terms)",
                    confidence="low",
                )

        return None

    async def suggest_for_document(
        self,
        db: AsyncSession,
        doc: Document,
        metadata: Optional[DocumentMetadata] = None,
        *,
        extra_text: str = "",
    ) -> Optional[CaseSuggestion]:
        search_text = " ".join(
            filter(
                None,
                [
                    doc.email_subject or "",
                    doc.filename or "",
                    (doc.content or "")[:8000],
                    extra_text or "",
                ],
            )
        )
        return await self.suggest_case(
            db,
            search_text=search_text,
            org_id=doc.organization_id,
            metadata=metadata,
        )


case_suggestion_service = CaseSuggestionService()
