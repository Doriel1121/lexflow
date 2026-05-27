"""
Document Processing Pipeline - Sequential Architecture
=======================================================

Architecture Decision: Single Sequential Task
---------------------------------------------
Previous approach used Celery chord/group (parallel map/reduce).
Problem: When tasks hit API rate limits and retry (via autoretry_for),
Celery's chord completion counter gets confused — it waits for exact 
task completions but retries are counted differently, causing deadlocks.

Solution: Single `process_document_pipeline` Celery task that runs
all phases sequentially with inline retry loops. This is:
- Reliable: no chord deadlocks
- Observable: progress updates at every step
- Recoverable: each chunk retries independently up to 15 times

Changes from previous version:
- Redis pub/sub for real-time WebSocket notifications (no DB polling)
- Batched embedding tasks (EMBEDDING_BATCH_SIZE chunks per task)
- Atomic completion detection to prevent race conditions
- asyncio.sleep instead of time.sleep to avoid blocking workers
"""

import asyncio
import logging
import time
from celery import shared_task
from app.core.config import settings
from app.db.session import CeleryAsyncSessionLocal
from app.crud.document import document_crud
from app.db.models.document import DocumentProcessingStatus, DocumentChunk, Document
from app.services.ocr import ocr_service
from app.services.document_chunker import document_chunker
from app.services.ai.ner_service import ner_service
from app.services.text_normalization import text_normalization_service
from app.db.models.deadline import Deadline, DeadlineType
import dateparser
from app.services.document_intelligence import document_intelligence_service
from app.services.llm import llm_service
from app.services.ai_utils import valid_embedding
from app.services.document_notifications import create_org_notification
from app.services.document_pipeline import run_document_pipeline
from app.services.processing_telemetry import emit_stage, record_processing_error
from sqlalchemy import select, delete, update, text
from app.db.models.document_processing_log import DocumentProcessingLog
import traceback as tb

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine inside a synchronous Celery task."""
    return asyncio.run(coro)


# ── Batched embedding task ────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5, retry_backoff=True)
def embed_chunk_batch_task(self, document_id: int, chunk_ids: list[int]):
    """Generate embeddings for a BATCH of chunks and update document progress.
    Instead of 1 task per chunk, we process multiple chunks per task to reduce
    Celery overhead and Redis queue pressure.
    """
    async def _run():
        if not chunk_ids:
            return

        async with CeleryAsyncSessionLocal() as db:
            # Load chunks in one query, then preserve original order.
            res = await db.execute(
                select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
            )
            found = {c.id: c for c in res.scalars().all()}
            ordered_chunks = [found.get(cid) for cid in chunk_ids]

            missing_count = sum(1 for c in ordered_chunks if c is None)
            if missing_count:
                logger.warning(
                    f"[Doc {document_id}] Missing {missing_count}/{len(chunk_ids)} chunks; counting as processed to avoid stalling."
                )

            texts: list[str] = [
                (c.text_content if c else "") for c in ordered_chunks
            ]
            vectors = await llm_service.generate_embeddings(texts)

            failed_in_batch = 0
            for chunk, vector in zip(ordered_chunks, vectors):
                if not chunk:
                    continue
                if valid_embedding(vector):
                    chunk.embedding = vector
                else:
                    failed_in_batch += 1

            doc = await document_crud.get(db, document_id)
            if doc and (failed_in_batch or missing_count):
                doc.embedding_failed_count = (doc.embedding_failed_count or 0) + (
                    failed_in_batch + missing_count
                )
                health = dict(doc.ai_health or {})
                health["embedding"] = "partial"
                doc.ai_health = health

            await db.commit()

            # IMPORTANT: Even failed/invalid embeddings must advance `processed_chunks`
            # or the document can get stuck in "embedding" forever.
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(processed_chunks=Document.processed_chunks + len(chunk_ids))
            )
            await db.commit()

            # Update progress based on processed_chunks.
            doc = await document_crud.get(db, document_id)
            if doc:
                total = max(doc.total_chunks or 0, 1)
                processed = doc.processed_chunks or 0
                doc.processing_stage = "embedding"
                doc.processing_progress = round(57.0 + (processed / total) * 38.0, 1)
                await db.commit()

        # ── Atomic completion check ───────────────────────────────────
        # Only ONE batch task will successfully flip the status to COMPLETED
        # because we use a WHERE clause that checks the current state.
        async with CeleryAsyncSessionLocal() as db:
            result = await db.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.processed_chunks >= Document.total_chunks,
                    Document.processing_stage != "completed",
                    Document.total_chunks > 0,
                )
                .values(
                    processing_status=DocumentProcessingStatus.COMPLETED,
                    processing_progress=100.0,
                )
            )
            await db.commit()

            if result.rowcount > 0:
                doc = await document_crud.get(db, document_id)
                if doc:
                    failed = doc.embedding_failed_count or 0
                    doc.processing_stage = (
                        "completed_embedding_partial" if failed > 0 else "completed"
                    )
                    health = dict(doc.ai_health or {})
                    health["embedding"] = "partial" if failed > 0 else "ok"
                    doc.ai_health = health
                    await db.commit()
                logger.info(f"[Doc {document_id}] ✅ All embeddings done (this batch won the race).")
                doc = await document_crud.get(db, document_id)
                if doc:
                    emit_stage(
                        document_id=document_id,
                        organization_id=doc.organization_id,
                        stage="embedding_batch_complete",
                        duration_ms=0,
                        status="ok",
                        failed_chunks=doc.embedding_failed_count or 0,
                    )
                    try:
                        await create_org_notification(
                            db,
                            organization_id=doc.organization_id,
                            event_type="DOCUMENT_PROCESSED",
                            title="Document Processed",
                            message=f"Document '{doc.filename}' is ready.",
                            source_type="document",
                            source_id=document_id,
                        )
                    except Exception as broadcast_err:
                        logger.error(f"[Doc {document_id}] Completion notification failed: {broadcast_err}", exc_info=True)

    run_async(_run())


# Keep backward-compatible single-chunk task (delegates to batch)
@shared_task(bind=True, max_retries=5, retry_backoff=True)
def embed_chunk_task(self, document_id: int, chunk_id: int):
    """Legacy single-chunk task — delegates to batch task."""
    embed_chunk_batch_task.delay(document_id, [chunk_id])


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def process_document_pipeline(self, document_id: int, file_path: str, user_id: int, organization_id: int):
    """
    Entry point for the document processing pipeline (called by upload API).
    Runs the complete pipeline in a single sequential task.
    """
    logger.info(f"[Doc {document_id}] Pipeline started. file_path={file_path}")

    def _queue_embed_batch(doc_id: int, batch_ids: list[int]) -> None:
        from app.core.celery import safe_task_delay
        safe_task_delay(embed_chunk_batch_task, document_id=doc_id, chunk_ids=batch_ids)

    async def _run():
        await run_document_pipeline(
            document_id,
            file_path,
            user_id,
            organization_id,
            session_factory=CeleryAsyncSessionLocal,
            allow_embed_fanout=True,
            queue_embed_batch=_queue_embed_batch,
        )
    try:
        run_async(_run())
    except Exception as exc:
        try:
            asyncio.run(_log_top_level_failure(document_id, exc))
        except Exception:
            pass


async def _log_top_level_failure(document_id: int, exc: Exception) -> None:
    """Capture any pipeline failures that escape the main _run coroutine."""
    async with CeleryAsyncSessionLocal() as db:
        doc = await document_crud.get(db, document_id)
        org_id = doc.organization_id if doc else None
        await record_processing_error(
            db,
            document_id=document_id,
            organization_id=org_id,
            stage="top_level",
            error=exc,
        )
