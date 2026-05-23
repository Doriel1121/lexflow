"""Organization-scoped AI / document processing health metrics."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentProcessingStatus
from app.db.models.document_processing_log import DocumentProcessingLog
from app.services.processing_telemetry import get_ai_provider_name


class AiHealthAnalyticsService:
    async def get_org_ai_health(self, db: AsyncSession, org_id: int) -> Dict[str, Any]:
        now = datetime.utcnow()
        since_7d = now - timedelta(days=7)

        base = Document.organization_id == org_id

        total_documents = await db.scalar(
            select(func.count(Document.id)).where(base)
        ) or 0

        processing_now = await db.scalar(
            select(func.count(Document.id)).where(
                base,
                Document.processing_status.in_(
                    [DocumentProcessingStatus.PENDING, DocumentProcessingStatus.PROCESSING]
                ),
            )
        ) or 0

        failed_documents = await db.scalar(
            select(func.count(Document.id)).where(
                base, Document.processing_status == DocumentProcessingStatus.FAILED
            )
        ) or 0

        without_ai = await db.scalar(
            select(func.count(Document.id)).where(
                base,
                or_(
                    Document.processing_stage == "completed_without_ai",
                    Document.classification.in_(
                        ["Text Extracted (AI Pending)", "Pending Analysis"]
                    ),
                ),
            )
        ) or 0

        embedding_issues = await db.scalar(
            select(func.count(Document.id)).where(
                base,
                or_(
                    Document.processing_stage == "completed_embedding_partial",
                    Document.embedding_failed_count > 0,
                ),
            )
        ) or 0

        chunked_analysis = await db.scalar(
            select(func.count(Document.id)).where(
                base,
                Document.ai_health.isnot(None),
                Document.ai_health.contains({"analysis_mode": "chunked"}),
            )
        ) or 0

        full_analysis = await db.scalar(
            select(func.count(Document.id)).where(
                base,
                Document.ai_health.isnot(None),
                Document.ai_health.contains({"analysis_mode": "full"}),
            )
        ) or 0

        total_chunks = await db.scalar(
            select(func.coalesce(func.sum(Document.total_chunks), 0)).where(
                base, Document.total_chunks > 0
            )
        ) or 0

        failed_embedding_units = await db.scalar(
            select(func.coalesce(func.sum(Document.embedding_failed_count), 0)).where(base)
        ) or 0

        embedding_failure_rate = round(
            (failed_embedding_units / max(int(total_chunks), 1)) * 100, 1
        )

        errors_7d = await db.scalar(
            select(func.count(DocumentProcessingLog.id)).where(
                DocumentProcessingLog.organization_id == org_id,
                DocumentProcessingLog.event_type == "error",
                DocumentProcessingLog.created_at >= since_7d,
            )
        ) or 0

        recent_errors = await self._recent_errors(db, org_id, limit=8)

        healthy = max(total_documents - without_ai - embedding_issues - failed_documents, 0)
        health_score = round(
            (healthy / max(total_documents, 1)) * 100, 1
        )

        return {
            "organization_id": org_id,
            "provider": get_ai_provider_name(),
            "total_documents": total_documents,
            "processing_now": processing_now,
            "failed_documents": failed_documents,
            "completed_without_ai": without_ai,
            "embedding_issues": embedding_issues,
            "chunked_analysis_documents": chunked_analysis,
            "full_analysis_documents": full_analysis,
            "embedding_failure_rate_percent": embedding_failure_rate,
            "processing_errors_7d": errors_7d,
            "health_score_percent": health_score,
            "recent_errors": recent_errors,
        }

    async def _recent_errors(
        self, db: AsyncSession, org_id: int, limit: int = 8
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(
                DocumentProcessingLog,
                Document.filename,
            )
            .join(Document, Document.id == DocumentProcessingLog.document_id)
            .where(
                DocumentProcessingLog.organization_id == org_id,
                DocumentProcessingLog.event_type == "error",
            )
            .order_by(DocumentProcessingLog.created_at.desc())
            .limit(limit)
        )
        rows = []
        for log, filename in result.all():
            rows.append(
                {
                    "document_id": log.document_id,
                    "filename": filename,
                    "stage": log.stage,
                    "message": (log.error_message or "")[:200],
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
            )
        return rows


ai_health_analytics_service = AiHealthAnalyticsService()
