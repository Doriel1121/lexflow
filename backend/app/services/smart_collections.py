"""
Smart Collections Service
=========================
Automatically assigns documents to the correct tag-based collections
based on the structured AI analysis result produced by DocumentIntelligenceService.

Collection categories recognised
---------------------------------
  client_id   – ISO / Israeli 9-digit IDs, passport numbers, tax IDs found on parties
  project     – Explicit project / matter names from document text
  organization – Company / firm names found in parties
  case_type   – High-level document type  (Contract, Litigation, Real Estate …)
  document_type – Fine-grained document sub-type (NDA, Lease Agreement, Power of Attorney …)
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.document import Document as DBDocument
from app.crud.tag import crud_tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Company-name suffixes (English + Hebrew) used to detect organisations
# ---------------------------------------------------------------------------
_COMPANY_SUFFIXES_RE = re.compile(
    r"\b(?:Inc|LLC|Ltd|Corp|LLP|LP|Co|PLC|GmbH|S\.A|N\.V|בע\"מ|ב\.מ\.)\b",
    re.IGNORECASE | re.UNICODE,
)

# Minimum length to avoid tiny noise tokens
_MIN_TAG_LEN = 2
# Maximum to keep sane collection names
_MAX_TAG_LEN = 80

# Strings Gemini sometimes returns instead of a real null / unknown value
_JUNK_VALUES = frozenset({
    "null", "none", "n/a", "na", "unknown", "unclassified",
    "not found", "not available", "not applicable", "n.a.", "—", "-",
})


def _clean(value: str) -> Optional[str]:
    """Strip whitespace and return None if too short, too long, or a junk Gemini value."""
    v = (value or "").strip()
    if v.lower() in _JUNK_VALUES:
        return None
    if _MIN_TAG_LEN <= len(v) <= _MAX_TAG_LEN:
        return v
    return None


# Common noise tokens to exclude from AI tags
_STOPWORDS = frozenset({
    "document", "documents", "agreement", "contract", "legal", "case",
    "party", "parties", "unknown", "general", "misc", "other",
})


def _normalize_tag(value: str) -> Optional[str]:
    """Normalize AI tag text to a stable, UI-friendly form."""
    v = _clean(value)
    if not v:
        return None
    v = re.sub(r"[_\\-]+", " ", v)
    v = re.sub(r"\\s+", " ", v).strip()
    if not v:
        return None
    if v.lower() in _STOPWORDS:
        return None
    # Title-case for display consistency
    return v[:1].upper() + v[1:]


def _is_company(name: str) -> bool:
    return bool(_COMPANY_SUFFIXES_RE.search(name))


class SmartCollectionsService:
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def route_document_to_collections(
        self,
        db: AsyncSession,
        document: DBDocument,
        ai_analysis: Dict[str, Any],
    ) -> None:
        """
        Read the AI analysis result and assign the document to the
        appropriate tag-based collections.  Safe to call multiple times
        (idempotent — duplicate links are skipped).
        """
        try:
            org_id = document.organization_id
            tags_to_add = []

            # 1. client_id — party id_numbers + regex routing_ids already
            #    extracted by MetadataExtractionService (stored in ai_analysis
            #    as routing_ids when passed through, or from parties).
            tags_to_add += await self._tags_for_client_ids(db, ai_analysis, org_id)

            # 2. project — regex routing_projects
            tags_to_add += await self._tags_for_projects(db, ai_analysis, org_id)

            # 3. organization — company party names
            tags_to_add += await self._tags_for_organizations(db, ai_analysis, org_id)

            # 4. case_type — document_type field
            tags_to_add += await self._tags_for_case_type(db, ai_analysis, org_id)

            # 5. document_type — document_subtype field
            tags_to_add += await self._tags_for_document_type(db, ai_analysis, org_id)

            # 6. AI tags — generic tags field from AI analysis
            tags_to_add += await self._tags_for_ai_tags(db, ai_analysis, org_id)

            if not tags_to_add:
                return

            # Reload the document with its current tags to avoid stale state
            result = await db.execute(
                select(DBDocument)
                .options(selectinload(DBDocument.tags))
                .filter(DBDocument.id == document.id)
            )
            fresh_doc = result.scalars().first()
            if not fresh_doc:
                return

            existing_tag_ids = {t.id for t in fresh_doc.tags}
            added = 0
            for tag in tags_to_add:
                if tag.id not in existing_tag_ids:
                    fresh_doc.tags.append(tag)
                    existing_tag_ids.add(tag.id)
                    added += 1

            if added:
                await db.commit()
                logger.info(
                    "SmartCollections: added %d collection(s) to document %d",
                    added,
                    document.id,
                )

        except Exception as exc:
            logger.error(
                "SmartCollections: failed to route document %d: %s",
                document.id,
                exc,
            )
            # Never let collection routing crash the processing pipeline
            try:
                await db.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Private helpers — each returns a list of Tag ORM objects
    # ------------------------------------------------------------------

    async def _tags_for_client_ids(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Extract IDs from party records and from routing_ids (regex pass)."""
        seen: set[str] = set()
        tags = []

        # From AI structured parties
        for party in ai_analysis.get("parties", []):
            raw = party.get("id_number") or ""
            id_val = _clean(raw)
            if id_val and id_val not in seen:
                seen.add(id_val)
                t = await crud_tag.find_or_create(
                    db, name=id_val, category="client_id", organization_id=org_id
                )
                tags.append(t)

        # From regex routing_ids already in ai_analysis (passed through from
        # MetadataExtractionService when called earlier in the pipeline)
        for rid in ai_analysis.get("routing_ids", []):
            id_val = _clean(str(rid))
            if id_val and id_val not in seen:
                seen.add(id_val)
                t = await crud_tag.find_or_create(
                    db, name=id_val, category="client_id", organization_id=org_id
                )
                tags.append(t)

        return tags

    async def _tags_for_projects(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Extract project names from routing_projects (regex)."""
        seen: set[str] = set()
        tags = []
        for proj in ai_analysis.get("routing_projects", []):
            name = _clean(str(proj))
            if name and name not in seen:
                seen.add(name)
                t = await crud_tag.find_or_create(
                    db, name=name, category="project", organization_id=org_id
                )
                tags.append(t)
        return tags

    async def _tags_for_organizations(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Extract company names from AI party records."""
        seen: set[str] = set()
        tags = []
        for party in ai_analysis.get("parties", []):
            raw_name = (party.get("name") or "").strip()
            if not raw_name:
                continue
            if not _is_company(raw_name):
                continue
            name = _clean(raw_name)
            if name and name not in seen:
                seen.add(name)
                t = await crud_tag.find_or_create(
                    db, name=name, category="organization", organization_id=org_id
                )
                tags.append(t)

        # Also use routing_organizations if pre-extracted by MetadataExtractionService
        for org_name in ai_analysis.get("routing_organizations", []):
            name = _clean(str(org_name))
            if name and name not in seen:
                seen.add(name)
                t = await crud_tag.find_or_create(
                    db, name=name, category="organization", organization_id=org_id
                )
                tags.append(t)

        return tags

    async def _tags_for_case_type(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Map document_type → case_type collection."""
        doc_type = _clean(ai_analysis.get("document_type", "") or "")
        if not doc_type or doc_type.lower() in ("unknown", "unclassified", ""):
            return []
        t = await crud_tag.find_or_create(
            db, name=doc_type, category="case_type", organization_id=org_id
        )
        return [t]

    async def _tags_for_document_type(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Map document_subtype → document_type collection."""
        subtype = _clean(ai_analysis.get("document_subtype", "") or "")
        if not subtype or subtype.lower() in ("unknown", "unclassified", ""):
            return []
        t = await crud_tag.find_or_create(
            db, name=subtype, category="document_type", organization_id=org_id
        )
        return [t]

    async def _tags_for_ai_tags(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Process the generic 'tags' list from AI analysis."""
        seen: set[str] = set()
        tags = []

        # Support confidence-weighted tags (preferred)
        tag_votes = ai_analysis.get("tag_votes") or []
        if isinstance(tag_votes, list) and tag_votes:
            # Deduplicate by normalized name with highest confidence
            best: dict[str, float] = {}
            for item in tag_votes:
                if isinstance(item, dict):
                    raw = item.get("name") or item.get("tag") or ""
                    conf = float(item.get("confidence", 0.0) or 0.0)
                else:
                    raw = str(item)
                    conf = 0.0
                name = _normalize_tag(raw)
                if not name:
                    continue
                best[name] = max(best.get(name, 0.0), conf)

            # Keep only above threshold
            min_conf = float(settings.AI_TAG_MIN_CONFIDENCE or 0.0)
            ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)
            for name, conf in ranked[: int(settings.AI_TAG_MAX_PER_DOCUMENT or 8)]:
                if conf < min_conf:
                    continue
                if name not in seen:
                    seen.add(name)
                    t = await crud_tag.find_or_create(
                        db, name=name, category="ai_tag", organization_id=org_id
                    )
                    tags.append(t)
            return tags

        # Fallback: raw string tags
        for tag_name in ai_analysis.get("tags", []):
            name = _normalize_tag(str(tag_name))
            if name and name not in seen:
                seen.add(name)
                t = await crud_tag.find_or_create(
                    db, name=name, category="ai_tag", organization_id=org_id
                )
                tags.append(t)

        # Limit volume to avoid noisy tagging
        return tags[: int(settings.AI_TAG_MAX_PER_DOCUMENT or 8)]


smart_collections_service = SmartCollectionsService()
