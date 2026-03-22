"""
Email Inbound Ingestion Service
================================
Processes a single email attachment through the full pipeline:
  FILE BYTES → storage → Document.create → background AI processing
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.email_config import EmailConfig
from app.db.models.document import Document, DocumentProcessingStatus
from app.crud.document import document_crud
from app.schemas.document import DocumentCreate
from app.services.storage import storage_service
from app.services.audit import log_audit
from app.services.document_processing_task import document_processing_service

logger = logging.getLogger(__name__)

# ── Allowed MIME types ────────────────────────────────────────────────────────
ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "image/",
    "application/msword",
    "application/vnd.openxmlformats",
    "application/octet-stream",   # Postman / some providers send this for PDFs
)

# Allowed extensions as fallback when MIME is generic
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".doc", ".docx"}

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20 MB


def _is_allowed(content_type: str, filename: str = "") -> bool:
    ct = (content_type or "").lower().split(";")[0].strip()
    if any(ct.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        return True
    ext = os.path.splitext(filename or "")[-1].lower()
    allowed_by_ext = ext in ALLOWED_EXTENSIONS
    if allowed_by_ext:
        logger.info("email_ingestion: MIME '%s' not whitelisted but extension '%s' is — accepting", ct, ext)
    return allowed_by_ext


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class EmailIngestionService:

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
        Run one attachment through the ingestion pipeline.
        Returns the created Document, or None if skipped.
        """
        logger.info(
            "email_ingestion: received '%s'  mime='%s'  size=%d bytes  from='%s'",
            filename, content_type, len(file_bytes), email_from,
        )

        # 1. MIME / extension guard
        if not _is_allowed(content_type, filename):
            logger.warning(
                "email_ingestion: SKIP — unsupported mime='%s' ext='%s' file='%s'",
                content_type, os.path.splitext(filename)[-1], filename,
            )
            return None

        # 2. Size guard
        if len(file_bytes) > MAX_ATTACHMENT_BYTES:
            logger.warning(
                "email_ingestion: SKIP — file too large (%d bytes) '%s'",
                len(file_bytes), filename,
            )
            return None

        # 3. Duplicate check
        file_hash = _sha256(file_bytes)
        if await _is_duplicate(db, file_hash, config.organization_id):
            logger.info("email_ingestion: SKIP — duplicate file '%s' (hash=%s)", filename, file_hash[:12])
            return None

        logger.info("email_ingestion: all checks passed — starting ingestion for '%s'", filename)

        try:
            # 4. Save file to storage
            # save_file_bytes returns (url: str, absolute_path: Path)
            folder = "inbox/email_inbound"
            s3_url, file_path = await storage_service.save_file_bytes(
                file_bytes, folder, filename
            )
            logger.info("email_ingestion: saved to storage → url=%s  path=%s", s3_url, file_path)

            # 5. Create Document placeholder in DB
            owner_id = config.user_id
            doc_in = DocumentCreate(
                filename=filename,
                s3_url=s3_url,
                case_id=None,
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
            logger.info("email_ingestion: document record created → id=%d", document.id)

            # 6. Stamp email provenance fields
            document.ingestion_method  = "email_inbound"
            document.email_from        = email_from
            document.email_subject     = email_subject
            document.email_received_at = email_received_at
            document.organization_id   = config.organization_id
            document.processing_status = DocumentProcessingStatus.PENDING
            db.add(document)
            await db.commit()
            logger.info("email_ingestion: provenance stamped and committed for doc_id=%d", document.id)

            # 7. Queue background AI processing
            try:
                from app.workers.document_tasks import process_document_pipeline
                process_document_pipeline.delay(
                    document_id=document.id,
                    file_path=str(file_path),
                    user_id=owner_id,
                    organization_id=config.organization_id,
                )
                logger.info("email_ingestion: Celery task queued for doc_id=%d", document.id)
            except Exception as celery_err:
                # Celery not available → fall back to in-process background task
                logger.warning(
                    "email_ingestion: Celery unavailable (%s) — falling back to background task",
                    celery_err,
                )
                import asyncio
                asyncio.create_task(
                    document_processing_service.process_document_background(
                        document_id=document.id,
                        file_path=str(file_path),
                        user_id=owner_id,
                        organization_id=config.organization_id,
                    )
                )

            # 8. Update config stats
            config.total_ingested  = (config.total_ingested or 0) + 1
            config.last_received_at = datetime.utcnow()
            db.add(config)
            await db.commit()

            # 9. Audit log (non-fatal)
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
                        "file_hash": file_hash,
                    },
                )
            except Exception as audit_err:
                logger.warning("email_ingestion: audit log failed (non-fatal): %s", audit_err)

            logger.info("email_ingestion: ✅ SUCCESS  doc_id=%d  file='%s'", document.id, filename)
            return document

        except Exception as exc:
            logger.error(
                "email_ingestion: ❌ EXCEPTION processing '%s': %s",
                filename, exc, exc_info=True,
            )
            try:
                await db.rollback()
            except Exception:
                pass
            return None


# Singleton
email_ingestion_service = EmailIngestionService()


async def _is_duplicate(db: AsyncSession, file_hash: str, org_id: Optional[int]) -> bool:
    """Return True if this exact file was already ingested for this org."""
    stmt = select(Document).where(
        Document.ingestion_method == "email_inbound",
        Document.email_subject    == f"__hash__{file_hash}",
    )
    if org_id:
        stmt = stmt.where(Document.organization_id == org_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
