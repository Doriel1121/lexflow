import re
import logging
from typing import List, Optional

from sqlalchemy import func, select, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document as DBDocument, document_tag_association
from app.db.models.tag import Tag as DBTag
from app.schemas.tag import TagCreate, TagUpdate

logger = logging.getLogger(__name__)

# Categories whose tags are global constants (no org scope, shared across all orgs).
# These represent semantic document types — not client data.
GLOBAL_CATEGORIES = frozenset({"case_type", "document_type"})

# Categories whose tags are strictly org-scoped (contain real client data).
ORG_SCOPED_CATEGORIES = frozenset({"client_id", "person", "organization", "project", "ai_tag"})

# Categories where fuzzy matching (token overlap) is used to unify near-duplicates.
# Never applied to client_id (exact IDs) or ai_tag (too broad).
_FUZZY_CATEGORIES = frozenset({"organization", "person", "project", "document_type"})

# Minimum token overlap ratio to consider two tag names as the same entity.
_FUZZY_THRESHOLD = 0.85


def _normalize_for_matching(name: str) -> str:
    """Produce a stable key for fuzzy comparison.

    Collapses whitespace, lowercases, strips common Hebrew/English
    corporate suffixes and prefixes so that:
      'חברת מגדלי העתיד בע"מ' and 'מגדלי העתיד יזמות ובנייה בע"מ'
    compare on their core tokens.
    """
    v = re.sub(r"\s+", " ", name).strip().lower()
    # Strip corporate suffixes
    v = re.sub(r"\b(?:inc|llc|ltd|corp|llp|lp|co|plc|gmbh|s\.a|n\.v|בע\"מ|ב\.מ\.)\b", "", v, flags=re.IGNORECASE | re.UNICODE)
    # Strip Hebrew company prefix
    v = re.sub(r"^(?:חברת|חברה|עמותת)\s+", "", v, flags=re.UNICODE)
    # Strip Hebrew title prefixes
    v = re.sub(r'^(?:מר|גב\'|גברת|עו"ד|ד"ר|פרופ\'|פרופ|רו"ח|mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?)\s+', "", v, flags=re.IGNORECASE | re.UNICODE)
    return re.sub(r"\s+", " ", v).strip()


def _token_overlap(a: str, b: str) -> float:
    """Compute symmetric token overlap ratio between two normalized strings."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    # Symmetric: overlap relative to the *smaller* set, so a substring of the
    # canonical name still matches.
    smaller = min(len(tokens_a), len(tokens_b))
    return len(intersection) / smaller if smaller else 0.0


class CRUDTag:

    # ------------------------------------------------------------------
    # Basic lookups
    # ------------------------------------------------------------------

    async def get(self, db: AsyncSession, tag_id: int) -> Optional[DBTag]:
        result = await db.execute(select(DBTag).filter(DBTag.id == tag_id))
        return result.scalars().first()

    async def get_by_name_and_org(
        self,
        db: AsyncSession,
        name: str,
        organization_id: int,
    ) -> Optional[DBTag]:
        """Strict org-scoped lookup: (name, organization_id)."""
        result = await db.execute(
            select(DBTag).filter(
                DBTag.name == name,
                DBTag.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_global_by_name_and_category(
        self,
        db: AsyncSession,
        name: str,
        category: str,
    ) -> Optional[DBTag]:
        """Global const lookup: (name, category) where organization_id IS NULL."""
        result = await db.execute(
            select(DBTag).filter(
                DBTag.name == name,
                DBTag.category == category,
                DBTag.organization_id.is_(None),
            )
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # List — returns org-scoped tags + global const tags linked to org docs
    # ------------------------------------------------------------------

    async def get_multi_by_organization(
        self,
        db: AsyncSession,
        organization_id: int,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
    ) -> List[DBTag]:
        """
        Return all collections visible to an organisation:

        1. Org-scoped tags (organization_id = this org)
        2. Global const tags (organization_id IS NULL) that are linked to at
           least one document belonging to this org.

        Document counts are scoped to this org only — never leak counts from
        other orgs.
        """
        # Subquery: count only documents belonging to this org per tag
        doc_count_sq = (
            select(
                document_tag_association.c.tag_id,
                func.count(document_tag_association.c.document_id).label("doc_count"),
            )
            .join(
                DBDocument,
                DBDocument.id == document_tag_association.c.document_id,
            )
            .filter(DBDocument.organization_id == organization_id)
            .group_by(document_tag_association.c.tag_id)
            .subquery()
        )

        # Tags linked to at least one doc in this org (used to filter globals)
        linked_tag_ids_sq = (
            select(document_tag_association.c.tag_id)
            .join(
                DBDocument,
                DBDocument.id == document_tag_association.c.document_id,
            )
            .filter(DBDocument.organization_id == organization_id)
            .scalar_subquery()
        )

        query = (
            select(DBTag, func.coalesce(doc_count_sq.c.doc_count, 0).label("doc_count"))
            .outerjoin(doc_count_sq, DBTag.id == doc_count_sq.c.tag_id)
            .filter(
                or_(
                    # Org-scoped tags
                    DBTag.organization_id == organization_id,
                    # Global const tags linked to this org's documents
                    and_(
                        DBTag.organization_id.is_(None),
                        DBTag.id.in_(linked_tag_ids_sq),
                    ),
                )
            )
        )

        if category:
            query = query.filter(DBTag.category == category)

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        rows = result.all()

        tags: List[DBTag] = []
        for row in rows:
            tag = row[0]
            tag.document_count = int(row[1])
            tags.append(tag)

        return tags

    # ------------------------------------------------------------------
    # Fuzzy similarity lookup
    # ------------------------------------------------------------------

    async def find_similar_in_category(
        self,
        db: AsyncSession,
        name: str,
        category: str,
        organization_id: Optional[int],
    ) -> Optional[DBTag]:
        """Find an existing tag that is a fuzzy match (token overlap ≥ threshold).

        Only used for categories in _FUZZY_CATEGORIES.
        Returns the best match if any, otherwise None.
        """
        if category not in _FUZZY_CATEGORIES:
            return None

        norm_name = _normalize_for_matching(name)
        if not norm_name:
            return None

        # Fetch candidate tags in the same org + category
        if category in GLOBAL_CATEGORIES:
            result = await db.execute(
                select(DBTag).filter(
                    DBTag.category == category,
                    DBTag.organization_id.is_(None),
                )
            )
        else:
            if not organization_id:
                return None
            result = await db.execute(
                select(DBTag).filter(
                    DBTag.category == category,
                    DBTag.organization_id == organization_id,
                )
            )

        candidates = result.scalars().all()
        best_match: Optional[DBTag] = None
        best_score = 0.0

        for candidate in candidates:
            norm_candidate = _normalize_for_matching(candidate.name)
            if not norm_candidate:
                continue
            # Exact normalized match
            if norm_candidate == norm_name:
                return candidate
            # Token overlap check
            score = _token_overlap(norm_name, norm_candidate)
            if score >= _FUZZY_THRESHOLD and score > best_score:
                best_score = score
                best_match = candidate

        if best_match:
            logger.debug(
                "Fuzzy matched tag '%s' → existing '%s' (score=%.2f, cat=%s)",
                name, best_match.name, best_score, category,
            )
        return best_match

    # ------------------------------------------------------------------
    # Create / find-or-create (two-tier)
    # ------------------------------------------------------------------

    async def find_or_create(
        self,
        db: AsyncSession,
        name: str,
        category: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> DBTag:
        """
        Two-tier find-or-create based on category:

        Global const (case_type, document_type):
            Look up by (name, category) where org IS NULL.
            Create with organization_id=NULL if not found.
            Never scoped to an org — shared across all tenants.

        Org-scoped (client_id, person, organization, project, ai_tag):
            Look up strictly by (name, organization_id).
            Try fuzzy matching for applicable categories.
            Create with the org's organization_id if not found.
            Never falls back to global. Never crosses orgs.
        """
        is_global = category in GLOBAL_CATEGORIES

        if is_global:
            # --- Global const path ---
            tag = await self.get_global_by_name_and_category(db, name, category)
            if tag:
                return tag

            # Try fuzzy match for document_type (avoids near-duplicate subtypes)
            fuzzy = await self.find_similar_in_category(db, name, category, None)
            if fuzzy:
                return fuzzy

            db_tag = DBTag(name=name, category=category, organization_id=None)
            db.add(db_tag)
            try:
                await db.commit()
                await db.refresh(db_tag)
            except IntegrityError:
                await db.rollback()
                # Race condition: another worker created it — fetch and return
                tag = await self.get_global_by_name_and_category(db, name, category)
                if tag:
                    return tag
                raise
            return db_tag

        else:
            # --- Org-scoped path ---
            if not organization_id:
                # No org context — skip tag creation entirely to avoid
                # infinite recursion and orphaned global tags.
                logger.warning(
                    "find_or_create called with org-scoped category '%s' but "
                    "organization_id=None. Skipping tag '%s'.",
                    category, name,
                )
                # Return a transient (unsaved) tag object so callers don't crash
                return DBTag(name=name, category=category or "ai_tag", organization_id=None)

            # Exact match first
            tag = await self.get_by_name_and_org(db, name, organization_id)
            if tag:
                # Update category if a more specific one is now known
                if category and tag.category != category:
                    tag.category = category
                    await db.commit()
                    await db.refresh(tag)
                return tag

            # Fuzzy match for applicable categories
            fuzzy = await self.find_similar_in_category(db, name, category, organization_id)
            if fuzzy:
                return fuzzy

            db_tag = DBTag(
                name=name,
                category=category,
                organization_id=organization_id,
            )
            db.add(db_tag)
            try:
                await db.commit()
                await db.refresh(db_tag)
            except IntegrityError:
                await db.rollback()
                # Race condition: fetch the winner
                tag = await self.get_by_name_and_org(db, name, organization_id)
                if tag:
                    return tag
                raise
            return db_tag

    # ------------------------------------------------------------------
    # Update (rename)
    # ------------------------------------------------------------------

    async def update(
        self, db: AsyncSession, tag_id: int, tag_in: TagUpdate
    ) -> Optional[DBTag]:
        db_tag = await self.get(db, tag_id)
        if not db_tag:
            return None

        update_data = tag_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_tag, field, value)

        try:
            await db.commit()
            await db.refresh(db_tag)
        except IntegrityError:
            await db.rollback()
            raise  # Caller (endpoint) converts to 409

        return db_tag

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, db: AsyncSession, tag_id: int) -> Optional[DBTag]:
        db_tag = await self.get(db, tag_id)
        if not db_tag:
            return None
        await db.delete(db_tag)
        await db.commit()
        return db_tag

    # ------------------------------------------------------------------
    # Document count helper (used by DELETE endpoint for confirm dialog)
    # ------------------------------------------------------------------

    async def get_document_count(
        self,
        db: AsyncSession,
        tag_id: int,
        organization_id: int,
    ) -> int:
        """Count documents linked to this tag that belong to the given org."""
        result = await db.execute(
            select(func.count())
            .select_from(document_tag_association)
            .join(DBDocument, DBDocument.id == document_tag_association.c.document_id)
            .filter(
                document_tag_association.c.tag_id == tag_id,
                DBDocument.organization_id == organization_id,
            )
        )
        return result.scalar() or 0


crud_tag = CRUDTag()
