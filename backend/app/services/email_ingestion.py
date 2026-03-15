"""
Email Inbound Ingestion Service
================================
Processes a single email attachment through the full pipeline:
  FILE BYTES → OCR → AI Analysis → Smart Router → Document.create → Smart Collections → Audit Log
"""
from __future__ import annotations

import hashlib
import logging
import tempfile
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.email_config import EmailConfig
from app.db.models.document import Document, DocumentProcessingStatus
from app.crud.document import document_crud
from app.schemas.document import DocumentCreate
from app.services.ocr import ocr_service
from app.services.document_intelligence import DocumentIntelligenceService
from app.services.smart_router import smart_router
from app.services.smart_collections import smart_collections_service
from app.services.storage import storage_service
from app.services.audit import log_audit
from app.services.document_processing_task import document_processing_service
from app.api.ws.notifications import notification_manager

logger = logging.getLogger(__name__)

# ---- Supported attachment MIME types ----------------------------------------
ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "image/",
    "application/msword",
    "application/vnd.openxmlformats",
)

# Max attachment size: 20 MB
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


def _is_allowed(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return any(ct.startswith(p) for p in ALLOWED_MIME_PREFIXES)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _find_duplicate(db: AsyncSession, file_hash: str, org_id: Optional[int]) -> bool:
    """Return True if a document with the same SHA-256 already exists for this org."""
    stmt = select(Document).where(Document.email_subject == f"__hash__{file_hash}")
    # We reuse email_subject as a cheap hash store to avoid a new column.
    # A cleaner approach would add a file_hash column — acceptable as a follow-up.
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


class EmailIngestionService:
    def __init__(self):
        self._doc_intelligence = DocumentIntelligenceService()

    async def process_attachment(
        self,
        db: AsyncSession,
        *,
        config: EmailConfig,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        email_from: str,
        email_subject: str,
        email_received_at: datetime,
    ) -> Optional[Document]:
        """
        Run one attachment through the full ingestion pipeline.
        Returns the created Document or None if skipped.
        """
        # 1. Content-type guard
        if not _is_allowed(content_type):
            logger.info("Inbound email: skipping unsupported MIME '%s' (%s)", content_type, filename)
            return None

        # 2. Size guard
        if len(file_bytes) > MAX_ATTACHMENT_BYTES:
            logger.warning("Inbound email: attachment too large (%d bytes), skipping %s", len(file_bytes), filename)
            return None

        # 3. SHA-256 deduplication
        file_hash = _sha256(file_bytes)
        if await _is_duplicate(db, file_hash, config.organization_id):
            logger.info("Inbound email: duplicate attachment skipped (%s)", filename)
            return None

        logger.info("Inbound email: processing '%s' from %s", filename, email_from)

        try:
            # 4. Persist file to storage
            folder = "inbox/email_inbound"
            file_path_str, s3_url = await storage_service.save_file_bytes(file_bytes, folder, filename)

            # Get actual file path for background OCR processing
            file_path = await storage_service.get_file_path(f"{folder}/{filename}")

            # 5. Create Document record placeholder
            owner_id = config.user_id
            doc_in = DocumentCreate(
                filename=filename,
                s3_url=s3_url,
                case_id=None,  # Smart collections will route to case later
                content="Processing text...",
                classification="Pending Analysis",
                language=None,
                page_count=0,
            )
            document = await document_crud.create(
                db,
                doc_in,
                uploaded_by_user_id=owner_id,
                organization_id=config.organization_id,
            )

            # Stamp ingestion provenance directly
            document.ingestion_method = "email_inbound"
            document.email_from = email_from
            document.email_subject = email_subject
            document.email_received_at = email_received_at
            document.organization_id = config.organization_id
            document.processing_status = DocumentProcessingStatus.PENDING
            db.add(document)
            
            # Commit early so the document exists for relations
            await db.commit()
            
            from app.workers.document_tasks import process_document_pipeline
            # 6. Queue Celery Task for Heavy AI OCR & Summarization & Vector Embeddings
            process_document_pipeline.delay(
                document_id=document.id,
                file_path=str(file_path),
                user_id=owner_id,
                organization_id=config.organization_id
            )

            # 7. Update config stats
            config.total_ingested = (config.total_ingested or 0) + 1
            config.last_received_at = datetime.utcnow()
            db.add(config)
            await db.commit()

            # 12. Audit log
            try:
                await log_audit(
                    db,
                    event_type="email_document_auto_ingested",
                    organization_id=config.organization_id,
                    user_id=owner_id,
                    resource_type="document",
                    resource_id=str(document.id),
                    metadata_json={
                        "from": email_from,
                        "subject": email_subject,
                        "filename": filename,
                        "case_id": document.case_id,
                        "file_hash": file_hash,
                    }
                )
            except Exception as audit_err:
                logger.warning("Inbound email: audit log failed: %s", audit_err)

            logger.info(
                "Inbound email: ✅ ingested '%s' → doc_id=%d case_id=%s",
                filename, document.id, document.case_id
            )
            return document

        except Exception as exc:
            logger.error("Inbound email: ❌ failed to process '%s': %s", filename, exc, exc_info=True)
            try:
                await db.rollback()
            except Exception:
                pass
            return None


# Singleton
email_ingestion_service = EmailIngestionService()


async def _is_duplicate(db: AsyncSession, file_hash: str, org_id: Optional[int]) -> bool:
    """Check for a document already ingested from the same file bytes."""
    stmt = (
        select(Document)
        .where(
            Document.ingestion_method == "email_inbound",
            Document.email_subject == f"__hash__{file_hash}",
        )
    )
    if org_id:
        stmt = stmt.where(Document.organization_id == org_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
