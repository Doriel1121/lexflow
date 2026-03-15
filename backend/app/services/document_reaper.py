import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.db.models.document import Document, DocumentProcessingStatus
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def reap_stuck_documents() -> int:
    """
    Mark documents stuck in processing as completed_without_ai so the UI
    can surface a retry option instead of hanging forever.
    """
    max_minutes = settings.DOCUMENT_STUCK_MINUTES or 0
    if max_minutes <= 0:
        return 0

    cutoff = datetime.utcnow() - timedelta(minutes=max_minutes)
    processed = 0

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Document).where(
                Document.processing_status == DocumentProcessingStatus.PROCESSING,
                Document.updated_at < cutoff,
            )
        )
        docs = res.scalars().all()

        for doc in docs:
            doc.processing_status = DocumentProcessingStatus.COMPLETED
            doc.processing_stage = "completed_without_ai"
            doc.processing_progress = 100.0
            if not doc.classification:
                doc.classification = "Text Extracted (AI Pending)"
            processed += 1

        if processed:
            await db.commit()
            logger.warning("Reaper: marked %d document(s) as completed_without_ai", processed)

    return processed
