"""
Smart Collections Service
=========================
Automatically assigns documents to the correct tag-based collections
based on the structured AI analysis result produced by DocumentIntelligenceService.

Collection categories recognised
---------------------------------
  client_id     – ISO / Israeli 9-digit IDs, passport numbers, tax IDs found on parties
  person        – Natural person names (non-company parties)
  project       – Explicit project / matter names from document text
  organization  – Company / firm names found in parties
  case_type     – High-level document type  (Contract, Litigation, Real Estate …)
  document_type – Fine-grained document sub-type (NDA, Lease Agreement, Power of Attorney …)
  ai_tag        – Free-form topic tags extracted by AI

Per-category caps prevent tag flooding.  An overall budget of
MAX_TAGS_PER_DOCUMENT (default 8) trims low-value tags first.
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
# Constants & configuration
# ---------------------------------------------------------------------------

# Overall tag budget per document (across all categories)
MAX_TAGS_PER_DOCUMENT = 8

# Per-category caps: how many tags each category may contribute
_CATEGORY_CAPS: Dict[str, int] = {
    "client_id": 3,
    "person": 3,
    "organization": 2,
    "project": 1,
    "case_type": 1,
    "document_type": 1,
    "ai_tag": 4,
}

# Priority order for keeping tags when over budget (high → low value for
# cross-document unification).  Tags from categories listed first survive.
_CATEGORY_PRIORITY: List[str] = [
    "client_id",
    "person",
    "organization",
    "project",
    "case_type",
    "document_type",
    "ai_tag",
]

# ---------------------------------------------------------------------------
# Company-name suffixes (English + Hebrew) used to detect organisations
# ---------------------------------------------------------------------------
_COMPANY_SUFFIXES_RE = re.compile(
    r"""(?:Inc|LLC|Ltd|Corp|LLP|LP|Co|PLC|GmbH|S\.A|N\.V|בע"מ|ב\.מ\.)""",
    re.IGNORECASE | re.UNICODE,
)

# Minimum / maximum length to avoid tiny noise or excessively long tokens
_MIN_TAG_LEN = 2
_MAX_TAG_LEN = 80

# ---------------------------------------------------------------------------
# Junk value blocklist – strings AI / OCR return instead of real data
# ---------------------------------------------------------------------------
_JUNK_VALUES = frozenset({
    # English
    "null", "none", "n/a", "na", "unknown", "unclassified",
    "not found", "not available", "not applicable", "n.a.", "—", "-",
    # Hebrew placeholders
    "לא צוין", "לא מצוין", "לא ידוע", "אין", "ריק",
    "מספר", "page break",
})

# Regex patterns that indicate a placeholder / template value
_JUNK_PATTERNS_RE = re.compile(
    r"""
      ^\[.*\]$                  # [ח.פ. מספר] style bracket templates
    | לא\s+צוין                 # "לא צוין" anywhere in value
    | לא\s+מצוין                # "לא מצוין" anywhere in value
    | ^page\s*break$            # OCR artefact
    """,
    re.IGNORECASE | re.VERBOSE | re.UNICODE,
)

# Hebrew title prefixes to strip from person names
_TITLE_PREFIXES_RE = re.compile(
    r"""^(?:מר|גב'|גברת|עו"ד|ד"ר|פרופ'|פרופ|רו"ח|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)\s+""",
    re.IGNORECASE | re.UNICODE,
)

# Hebrew prefixes to strip from organization names (e.g. "חברת ...")
_ORG_PREFIX_RE = re.compile(
    r"^(?:חברת|חברה|עמותת)\s+",
    re.UNICODE,
)

# Common noise tokens to exclude from AI tags
_STOPWORDS = frozenset({
    "document", "documents", "agreement", "contract", "legal", "case",
    "party", "parties", "unknown", "general", "misc", "other",
})


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _clean(value: str) -> Optional[str]:
    """Collapse whitespace, strip junk, and enforce length limits."""
    v = (value or "")
    # Collapse all whitespace (newlines, tabs, etc.) into single spaces
    v = re.sub(r"\s+", " ", v).strip()
    # Normalize quotation marks
    v = v.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    if not v:
        return None
    if v.lower() in _JUNK_VALUES:
        return None
    if _JUNK_PATTERNS_RE.search(v):
        return None
    if _MIN_TAG_LEN <= len(v) <= _MAX_TAG_LEN:
        return v
    return None


def _normalize_org_name(raw: str) -> Optional[str]:
    """Normalize an organization name for consistent tag matching.

    Strips Hebrew prefixes (חברת), collapses OCR whitespace, and
    produces a canonical form.
    """
    v = _clean(raw)
    if not v:
        return None
    # Strip Hebrew company prefix
    v = _ORG_PREFIX_RE.sub("", v).strip()
    if not v or len(v) < _MIN_TAG_LEN:
        return None
    return v


def _normalize_person_name(raw: str) -> Optional[str]:
    """Normalize a person name for consistent tag matching.

    Strips title prefixes (מר, עו"ד, Dr., etc.) and collapses whitespace.
    """
    v = _clean(raw)
    if not v:
        return None
    # Strip title prefixes
    v = _TITLE_PREFIXES_RE.sub("", v).strip()
    if not v or len(v) < _MIN_TAG_LEN:
        return None
    return v


def _normalize_tag(value: str) -> Optional[str]:
    """Normalize AI tag text to a stable, UI-friendly form."""
    v = _clean(value)
    if not v:
        return None
    v = re.sub(r"[_\\-]+", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    if not v:
        return None
    if v.lower() in _STOPWORDS:
        return None
    # Title-case for display consistency
    return v[:1].upper() + v[1:]


def _is_company(name: str) -> bool:
    """Check if a party name looks like a company (has corporate suffix)."""
    return bool(_COMPANY_SUFFIXES_RE.search(name))


def _trim_by_priority(tags_by_category: Dict[str, list], budget: int) -> list:
    """Keep at most *budget* tags, preserving higher-priority categories first."""
    result: list = []
    for cat in _CATEGORY_PRIORITY:
        cat_tags = tags_by_category.get(cat, [])
        remaining = budget - len(result)
        if remaining <= 0:
            break
        result.extend(cat_tags[:remaining])
    return result


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
        doc_id = getattr(document, "id", None)
        try:
            org_id = document.organization_id

            # Collect tags per category (each method enforces its own cap)
            tags_by_category: Dict[str, list] = {}

            tags_by_category["client_id"] = await self._tags_for_client_ids(db, ai_analysis, org_id)
            tags_by_category["person"] = await self._tags_for_persons(db, ai_analysis, org_id)
            tags_by_category["organization"] = await self._tags_for_organizations(db, ai_analysis, org_id)
            tags_by_category["project"] = await self._tags_for_projects(db, ai_analysis, org_id)
            tags_by_category["case_type"] = await self._tags_for_case_type(db, ai_analysis, org_id)
            tags_by_category["document_type"] = await self._tags_for_document_type(db, ai_analysis, org_id)
            tags_by_category["ai_tag"] = await self._tags_for_ai_tags(db, ai_analysis, org_id)

            # Apply overall budget with priority trimming
            tags_to_add = _trim_by_priority(tags_by_category, MAX_TAGS_PER_DOCUMENT)

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
                await db.flush()
                await db.commit()
                logger.info("SmartCollections: added %d collection(s) to document %s", added, doc_id)

        except Exception as exc:
            logger.error(
                "SmartCollections: failed to route document %s: %s",
                doc_id,
                exc,
                exc_info=True,
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
        cap = _CATEGORY_CAPS.get("client_id", 3)
        seen: set[str] = set()
        tags = []

        # From AI structured parties
        for party in ai_analysis.get("parties", []):
            if not isinstance(party, dict):
                continue
            raw = party.get("id_number") or ""
            id_val = _clean(raw)
            if id_val and id_val not in seen:
                seen.add(id_val)
                t = await crud_tag.find_or_create(
                    db, name=id_val, category="client_id", organization_id=org_id
                )
                tags.append(t)
                if len(tags) >= cap:
                    return tags

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
                if len(tags) >= cap:
                    return tags

        return tags

    async def _tags_for_persons(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Extract natural person names from party records (non-companies)."""
        cap = _CATEGORY_CAPS.get("person", 3)
        seen: set[str] = set()
        tags = []

        for party in ai_analysis.get("parties", []):
            if not isinstance(party, dict):
                continue
            raw_name = (party.get("name") or "").strip()
            if not raw_name:
                continue
            # Skip companies — those go to _tags_for_organizations
            if _is_company(raw_name):
                continue
            name = _normalize_person_name(raw_name)
            if not name:
                continue
            # Use lowered form for dedup but store the normalized display form
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            t = await crud_tag.find_or_create(
                db, name=name, category="person", organization_id=org_id
            )
            tags.append(t)
            if len(tags) >= cap:
                return tags

        return tags

    async def _tags_for_projects(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Extract project names from routing_projects (regex)."""
        cap = _CATEGORY_CAPS.get("project", 1)
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
                if len(tags) >= cap:
                    return tags
        return tags

    async def _tags_for_organizations(
        self,
        db: AsyncSession,
        ai_analysis: Dict[str, Any],
        org_id: Optional[int],
    ) -> list:
        """Extract company names from AI party records."""
        cap = _CATEGORY_CAPS.get("organization", 2)
        seen: set[str] = set()
        tags = []

        for party in ai_analysis.get("parties", []):
            if not isinstance(party, dict):
                continue
            raw_name = (party.get("name") or "").strip()
            if not raw_name:
                continue
            if not _is_company(raw_name):
                continue
            name = _normalize_org_name(raw_name)
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            t = await crud_tag.find_or_create(
                db, name=name, category="organization", organization_id=org_id
            )
            tags.append(t)
            if len(tags) >= cap:
                return tags

        # Also use routing_organizations if pre-extracted by MetadataExtractionService
        for org_name in ai_analysis.get("routing_organizations", []):
            name = _normalize_org_name(str(org_name))
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            t = await crud_tag.find_or_create(
                db, name=name, category="organization", organization_id=org_id
            )
            tags.append(t)
            if len(tags) >= cap:
                return tags

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
        cap = _CATEGORY_CAPS.get("ai_tag", 4)
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
            for name, conf in ranked[:cap]:
                if conf < min_conf:
                    continue
                if name not in seen:
                    seen.add(name)
                    t = await crud_tag.find_or_create(
                        db, name=name, category="ai_tag", organization_id=org_id
                    )
                    tags.append(t)
            # If nothing passed the confidence threshold, fall back to raw tags
            # (some providers don't provide confidences; some pipelines supply
            # fixed/low values).
            if tags:
                return tags

        # Fallback: raw string tags
        raw_tags = ai_analysis.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.replace("\n", ",").split(",") if t.strip()]
        for tag_name in raw_tags or []:
            name = _normalize_tag(str(tag_name))
            if name and name not in seen:
                seen.add(name)
                t = await crud_tag.find_or_create(
                    db, name=name, category="ai_tag", organization_id=org_id
                )
                tags.append(t)
                if len(tags) >= cap:
                    break

        return tags[:cap]


smart_collections_service = SmartCollectionsService()
