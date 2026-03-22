"""
api/v1/endpoints/intake.py
===========================
AI Intake Center backend endpoint.

Transforms email-ingested documents into structured "Intake Items" with:
  - AI-generated insight (summary sentence)
  - Priority classification (low / medium / high / urgent)
  - Status tracking (needs_review / requires_action / auto_processed / completed)
  - Lightweight case suggestion (regex ID match → client name match → keyword match)
  - Deadline extraction from existing document intelligence

All data comes from existing tables — no new AI calls are made on every request.
We read from:  documents, document_metadata, deadlines, cases, clients, users
We write to:   documents (case_id), deadlines (confirm), cases (status)
"""

from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_db, RoleChecker, get_current_org
from app.db.models.user import User, UserRole
from app.db.models.document import Document, DocumentProcessingStatus
from app.db.models.document_metadata import DocumentMetadata
from app.db.models.case import Case, CaseStatus
from app.db.models.client import Client
from app.db.models.deadline import Deadline, DeadlineType
from app.services.audit import log_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intake", tags=["intake"])

_ORG_ROLES = RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])

# ─── Status constants ────────────────────────────────────────────────────────

STATUS_NEEDS_REVIEW    = "needs_review"
STATUS_REQUIRES_ACTION = "requires_action"
STATUS_AUTO_PROCESSED  = "auto_processed"
STATUS_COMPLETED       = "completed"

PRIORITY_URGENT = "urgent"
PRIORITY_HIGH   = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW    = "low"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _days_until(dt: datetime) -> int:
    return (dt.date() - datetime.utcnow().date()).days


def _derive_priority(doc: Document, deadlines: list) -> str:
    """Rule-based priority from deadline proximity and doc status."""
    if deadlines:
        closest = min(_days_until(d.deadline_date) for d in deadlines)
        if closest <= 3:
            return PRIORITY_URGENT
        if closest <= 7:
            return PRIORITY_HIGH
        if closest <= 14:
            return PRIORITY_MEDIUM
    if doc.processing_status == DocumentProcessingStatus.FAILED:
        return PRIORITY_HIGH
    return PRIORITY_LOW


def _derive_status(doc: Document) -> str:
    """Map document state to intake status."""
    if doc.case_id:
        return STATUS_COMPLETED
    if doc.processing_status == DocumentProcessingStatus.COMPLETED:
        return STATUS_REQUIRES_ACTION
    if doc.processing_status in (DocumentProcessingStatus.PENDING, DocumentProcessingStatus.PROCESSING):
        return STATUS_NEEDS_REVIEW
    return STATUS_NEEDS_REVIEW


def _build_ai_insight(doc: Document, metadata: Optional[DocumentMetadata], deadlines: list) -> str:
    """Build a short human-readable insight sentence from existing AI data."""
    parts = []

    if deadlines:
        closest_days = min(_days_until(d.deadline_date) for d in deadlines)
        if closest_days < 0:
            parts.append(f"⚠️ Deadline overdue by {abs(closest_days)} day(s)")
        elif closest_days == 0:
            parts.append("🚨 Deadline today")
        else:
            parts.append(f"📅 Deadline in {closest_days} day(s)")

    if doc.classification and doc.classification not in ("Pending Analysis", "Unknown", ""):
        parts.append(doc.classification)

    if metadata and metadata.entities:
        names = [
            (e.get("name") if isinstance(e, dict) else str(e))
            for e in (metadata.entities or [])[:2]
            if e
        ]
        if names:
            parts.append(f"Parties: {', '.join(filter(None, names))}")

    if not parts:
        if doc.processing_status == DocumentProcessingStatus.PROCESSING:
            return "AI is processing this document…"
        if doc.processing_status == DocumentProcessingStatus.FAILED:
            return "AI analysis failed — manual review required"
        return "Awaiting AI analysis"

    return " · ".join(parts)


async def _suggest_case(
    db: AsyncSession,
    doc: Document,
    metadata: Optional[DocumentMetadata],
    org_id: Optional[int],
) -> Optional[dict]:
    """
    Lightweight case suggestion:
      1. Case ID regex in subject/filename
      2. Client name match in entities
      3. Keyword match in case titles
    Returns {case_id, case_title, reason, confidence} or None.
    """
    base_query = select(Case).where(
        Case.status != CaseStatus.CLOSED,
        Case.organization_id == org_id if org_id else True,
    )

    search_text = f"{doc.email_subject or ''} {doc.filename or ''} {doc.content or ''}".lower()

    # 1. Case ID match
    id_match = re.search(r"case\s*[#\-]?\s*(\d+)", search_text, re.IGNORECASE)
    if id_match:
        cid = int(id_match.group(1))
        case = await db.get(Case, cid)
        if case and (not org_id or case.organization_id == org_id):
            return {"case_id": case.id, "case_title": case.title,
                    "reason": f"Case #{cid} found in subject/content", "confidence": "high"}

    # 2. Client name match from entities
    if metadata and metadata.entities:
        for ent in (metadata.entities or []):
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
                    return {"case_id": case.id, "case_title": case.title,
                            "reason": f"Client name match: {name}", "confidence": "medium"}

    # 3. Keyword match in case titles (words ≥ 4 chars, appear in both)
    words = [w for w in re.findall(r"\b\w{4,}\b", search_text) if w not in
             ("from", "subject", "dear", "regards", "with", "that", "this", "have", "been")]
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
            return {"case_id": best.id, "case_title": best.title,
                    "reason": f"Keyword match ({best_count} terms)", "confidence": "low"}

    return None


# ─── GET /intake — list items ─────────────────────────────────────────────────

@router.get("")
async def list_intake_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ROLES),
    org_id: Optional[int] = Depends(get_current_org),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """
    Return intake items — email-ingested documents enriched with AI insights.
    Ordered: urgent first, then by received date desc.
    """
    query = (
        select(Document)
        .options(selectinload(Document.deadlines))
        .where(Document.ingestion_method == "email_inbound")
    )
    if org_id:
        query = query.where(Document.organization_id == org_id)

    result = await db.execute(query.order_by(desc(Document.email_received_at)).limit(500))
    docs = result.scalars().all()

    # Load metadata for all docs in one query
    doc_ids = [d.id for d in docs]
    meta_result = await db.execute(
        select(DocumentMetadata).where(DocumentMetadata.document_id.in_(doc_ids))
    )
    meta_map = {m.document_id: m for m in meta_result.scalars().all()}

    items = []
    for doc in docs:
        meta = meta_map.get(doc.id)
        deadlines = list(doc.deadlines or [])
        priority = _derive_priority(doc, deadlines)
        derived_status = _derive_status(doc)

        if status_filter and derived_status != status_filter:
            continue

        suggestion = await _suggest_case(db, doc, meta, org_id)

        items.append({
            "id": doc.id,
            "subject": doc.email_subject or doc.filename,
            "from_address": doc.email_from,
            "received_at": doc.email_received_at.isoformat() if doc.email_received_at else None,
            "filename": doc.filename,
            "classification": doc.classification,
            "ai_insight": _build_ai_insight(doc, meta, deadlines),
            "priority": priority,
            "status": derived_status,
            "processing_status": doc.processing_status.value if doc.processing_status else "pending",
            "case_id": doc.case_id,
            "suggested_case": suggestion,
            "deadline_count": len(deadlines),
            "nearest_deadline_days": min((_days_until(d.deadline_date) for d in deadlines), default=None),
        })

    # Sort: urgent first, then high, then by received desc
    priority_order = {PRIORITY_URGENT: 0, PRIORITY_HIGH: 1, PRIORITY_MEDIUM: 2, PRIORITY_LOW: 3}
    items.sort(key=lambda x: (priority_order.get(x["priority"], 3), -(
        datetime.fromisoformat(x["received_at"]).timestamp()
        if x["received_at"] else 0
    )))

    total = len(items)
    items = items[offset: offset + limit]

    # Summary counts
    all_priorities = [_derive_priority(d, list(d.deadlines or [])) for d in docs]
    all_statuses = [_derive_status(d) for d in docs]

    return {
        "items": items,
        "total": total,
        "summary": {
            "total": len(docs),
            "needs_review": all_statuses.count(STATUS_NEEDS_REVIEW),
            "requires_action": all_statuses.count(STATUS_REQUIRES_ACTION),
            "auto_processed": all_statuses.count(STATUS_AUTO_PROCESSED),
            "completed": all_statuses.count(STATUS_COMPLETED),
            "urgent": all_priorities.count(PRIORITY_URGENT),
        },
    }


# ─── GET /intake/{doc_id} — item detail ──────────────────────────────────────

@router.get("/{doc_id}")
async def get_intake_item(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ROLES),
    org_id: Optional[int] = Depends(get_current_org),
):
    """Full detail for a single intake item — email content + AI panel data."""
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.deadlines),
            selectinload(Document.tags),
            selectinload(Document.summary),
            selectinload(Document.document_metadata),
        )
        .where(Document.id == doc_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Intake item not found")
    if org_id and doc.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    meta = doc.document_metadata
    deadlines = list(doc.deadlines or [])
    suggestion = await _suggest_case(db, doc, meta, org_id)

    # Fetch org lawyers for assignment dropdown
    lawyers_result = await db.execute(
        select(User).where(
            User.organization_id == org_id,
            User.role.in_([UserRole.LAWYER, UserRole.ORG_ADMIN]),
            User.is_active == True,
        )
    )
    lawyers = [{"id": u.id, "name": u.full_name or u.email} for u in lawyers_result.scalars().all()]

    def _norm_entities(raw):
        out = []
        for e in (raw or []):
            if isinstance(e, dict):
                out.append(e)
            elif isinstance(e, str):
                out.append({"name": e, "role": ""})
        return out

    return {
        "id": doc.id,
        "subject": doc.email_subject or doc.filename,
        "from_address": doc.email_from,
        "received_at": doc.email_received_at.isoformat() if doc.email_received_at else None,
        "filename": doc.filename,
        "body_preview": (doc.content or "")[:3000],
        "classification": doc.classification,
        "language": doc.language,
        "ai_insight": _build_ai_insight(doc, meta, deadlines),
        "priority": _derive_priority(doc, deadlines),
        "status": _derive_status(doc),
        "processing_status": doc.processing_status.value if doc.processing_status else "pending",
        "case_id": doc.case_id,
        "suggested_case": suggestion,
        "available_lawyers": lawyers,
        # AI panel data
        "ai": {
            "summary": doc.summary.content if doc.summary else None,
            "classification": doc.classification,
            "entities": _norm_entities(meta.entities if meta else []),
            "dates": meta.dates if meta else [],
            "amounts": meta.amounts if meta else [],
            "case_numbers": meta.case_numbers if meta else [],
            "deadlines": [
                {
                    "id": d.id,
                    "date": d.deadline_date.isoformat(),
                    "type": d.deadline_type.value if d.deadline_type else "other",
                    "description": d.description,
                    "days_until": _days_until(d.deadline_date),
                    "confidence": d.confidence_score,
                }
                for d in deadlines
            ],
        },
    }


# ─── POST /intake/{doc_id}/confirm — approve + link to case ──────────────────

class ConfirmIntakeRequest(BaseModel):
    case_id: int
    lawyer_id: Optional[int] = None
    confirm_deadlines: bool = True


@router.post("/{doc_id}/confirm")
async def confirm_intake_item(
    doc_id: int,
    body: ConfirmIntakeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ROLES),
    org_id: Optional[int] = Depends(get_current_org),
):
    """
    Confirm an intake item:
      1. Link document to case
      2. Optionally assign lawyer
      3. Confirm all extracted deadlines
      4. Audit log
    """
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if org_id and doc.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    case = await db.get(Case, body.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Link document → case
    doc.case_id = body.case_id
    db.add(doc)

    # 2. Optionally assign lawyer to case
    if body.lawyer_id:
        case.assigned_lawyer_id = body.lawyer_id
        db.add(case)

    # 3. Confirm extracted deadlines (link them to the case)
    if body.confirm_deadlines:
        result = await db.execute(
            select(Deadline).where(Deadline.document_id == doc_id)
        )
        for deadline in result.scalars().all():
            deadline.case_id = body.case_id
            deadline.organization_id = org_id
            db.add(deadline)

    await db.commit()

    # 4. Audit
    await log_audit(
        db=db,
        event_type="intake_confirmed",
        organization_id=org_id,
        user_id=current_user.id,
        resource_type="document",
        resource_id=str(doc_id),
        metadata_json={"case_id": body.case_id, "lawyer_id": body.lawyer_id},
    )

    return {"status": "confirmed", "document_id": doc_id, "case_id": body.case_id}


# ─── POST /intake/{doc_id}/dismiss ───────────────────────────────────────────

@router.post("/{doc_id}/dismiss")
async def dismiss_intake_item(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ROLES),
    org_id: Optional[int] = Depends(get_current_org),
):
    """Mark intake item as dismissed (classification = 'Dismissed')."""
    doc = await db.get(Document, doc_id)
    if not doc or (org_id and doc.organization_id != org_id):
        raise HTTPException(status_code=404, detail="Not found")

    doc.classification = "Dismissed"
    db.add(doc)
    await db.commit()

    await log_audit(
        db=db, event_type="intake_dismissed",
        organization_id=org_id, user_id=current_user.id,
        resource_type="document", resource_id=str(doc_id), metadata_json={},
    )
    return {"status": "dismissed"}
