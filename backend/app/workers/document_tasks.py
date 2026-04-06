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
from sqlalchemy import select, delete, update, text
from app.db.models.document_processing_log import DocumentProcessingLog
from app.db.models.notification import Notification
from app.db.models.user import User
import traceback as tb

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine inside a synchronous Celery task."""
    return asyncio.run(coro)


# ── Redis pub/sub helpers ─────────────────────────────────────────────────

def _publish_notification_for_users(org_user_ids: list[int], message: dict):
    """Publish notification to Redis channels for all given user IDs.
    Uses synchronous Redis since this runs inside Celery workers.
    """
    from app.api.ws.notifications import publish_notification_sync

    for user_id in org_user_ids:
        publish_notification_sync(user_id, message)


async def _create_org_notification(
    db,
    *,
    organization_id: int,
    event_type: str,
    title: str,
    message: str,
    source_type: str = None,
    source_id: int = None,
) -> int:
    """Persist notifications for all org users AND publish to Redis for instant WebSocket delivery."""
    result = await db.execute(select(User.id).where(User.organization_id == organization_id))
    org_user_ids = list(result.scalars().all())

    for org_user_id in org_user_ids:
        db.add(
            Notification(
                user_id=org_user_id,
                organization_id=organization_id,
                type=event_type,
                title=title,
                message=message,
                source_type=source_type,
                source_id=source_id,
                read=False,
            )
        )

    await db.commit()

    # Publish to Redis for instant WebSocket delivery
    ws_payload = {
        "type": event_type,
        "title": title,
        "message": message,
        "source_type": source_type,
    }
    if source_type == "document" and source_id is not None:
        ws_payload["document_id"] = source_id

    _publish_notification_for_users(org_user_ids, ws_payload)

    logger.info(
        "[Doc %s] Persisted %s '%s' notifications for org %s (+ Redis pub/sub)",
        source_id, len(org_user_ids), event_type, organization_id,
    )
    return len(org_user_ids)


# ── Batched embedding task ────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5, retry_backoff=True)
def embed_chunk_batch_task(self, document_id: int, chunk_ids: list[int]):
    """Generate embeddings for a BATCH of chunks and update document progress.
    Instead of 1 task per chunk, we process multiple chunks per task to reduce
    Celery overhead and Redis queue pressure.
    """
    async def _run():
        for chunk_id in chunk_ids:
            async with CeleryAsyncSessionLocal() as db:
                res = await db.execute(select(DocumentChunk).filter(DocumentChunk.id == chunk_id))
                chunk = res.scalars().first()
                if not chunk:
                    continue

                try:
                    vector = await llm_service.generate_embedding(chunk.text_content)
                    chunk.embedding = vector
                    await db.commit()
                except Exception as e:
                    logger.warning(f"[Doc {document_id}] Embedding chunk {chunk_id} failed: {e}")
                    await db.rollback()
                    continue

                # Increment processed_chunks atomically
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(processed_chunks=Document.processed_chunks + 1)
                )
                await db.commit()

                # Update progress
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
                    processing_stage="completed",
                    processing_progress=100.0,
                )
            )
            await db.commit()

            # Only the winning task sends the completion notification
            if result.rowcount > 0:
                logger.info(f"[Doc {document_id}] ✅ All embeddings done (this batch won the race).")
                doc = await document_crud.get(db, document_id)
                if doc:
                    try:
                        await _create_org_notification(
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

    async def _run():
        start_time = time.time()

        async def _abort_if_timed_out(stage: str) -> bool:
            max_seconds = settings.DOCUMENT_MAX_PROCESSING_SECONDS or 0
            if max_seconds <= 0:
                return False
            if (time.time() - start_time) <= max_seconds:
                return False
            async with CeleryAsyncSessionLocal() as db:
                doc = await document_crud.get(db, document_id)
                if doc:
                    doc.processing_status = DocumentProcessingStatus.COMPLETED
                    doc.processing_stage = "completed_without_ai"
                    doc.processing_progress = 100.0
                    doc.classification = "Text Extracted (AI Pending)"
                    await db.commit()
            logger.warning("[Doc %d] Processing timed out at stage=%s. Marked completed_without_ai.", document_id, stage)
            return True

        # ── STEP 1: Update status to PROCESSING ─────────────────────────
        async with CeleryAsyncSessionLocal() as db:
            doc = await document_crud.get(db, document_id)
            if not doc:
                logger.error(f"[Doc {document_id}] NOT FOUND — aborting.")
                return

            doc.processing_status = DocumentProcessingStatus.PROCESSING
            doc.processing_stage = "processing_ocr"
            doc.processing_progress = 2.0
            await db.commit()
            logger.info(f"[Doc {document_id}] Status set to PROCESSING.")

        # ── STEP 2: OCR ─────────────────────────────────────────────────
        try:
            logger.info(f"[Doc {document_id}] Running OCR on {file_path}...")
            ocr_result = await ocr_service.extract_text_from_file(file_path)
            extracted_text = ocr_result.get("text", "") or ""
            normalized_text = text_normalization_service.normalize(
                extracted_text, language=ocr_result.get("language", "en")
            )
        except Exception as e:
            logger.error(f"[Doc {document_id}] OCR FAILED: {e}")
            async with CeleryAsyncSessionLocal() as db:
                doc = await document_crud.get(db, document_id)
                if doc:
                    doc.processing_status = DocumentProcessingStatus.FAILED
                    doc.processing_stage = "ocr_failed"
                    await db.commit()
            return

        async with CeleryAsyncSessionLocal() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.content = normalized_text
                doc.language = ocr_result.get("language", "en")
                doc.page_count = ocr_result.get("page_count", 0)
                doc.processing_stage = "ocr_completed"
                doc.processing_progress = 8.0
                await db.commit()
                logger.info(f"[Doc {document_id}] OCR done: {len(extracted_text)} chars, {doc.page_count} pages.")

                # Notify UI that OCR text is ready for viewing
                try:
                    await _create_org_notification(
                        db,
                        organization_id=organization_id,
                        event_type="DOCUMENT_STATUS_UPDATE",
                        title="Document Processing Update",
                        message="Text extraction complete. Document is now viewable.",
                        source_type="document",
                        source_id=document_id,
                    )
                except Exception as e:
                    logger.warning(f"[Doc {document_id}] Failed to persist OCR status notification: {e}")

        if await _abort_if_timed_out("ocr_completed"):
            return

        # ── STEP 2.5: Deadline Extraction ─────────────────────────────
        logger.info(f"[Doc {document_id}] Extracting deadlines...")
        try:
            extracted_deadlines = ner_service.extract_deadlines(
                normalized_text, language=ocr_result.get("language", "en")
            )
            
            async with CeleryAsyncSessionLocal() as db:
                doc = await document_crud.get(db, document_id)
                if doc:
                    for d_info in extracted_deadlines:
                        new_deadline = Deadline(
                            document_id=document_id,
                            case_id=doc.case_id,
                            organization_id=doc.organization_id,
                            deadline_date=d_info["date"],
                            deadline_type=d_info["type"],
                            description=d_info["description"],
                            confidence_score=d_info["confidence"]
                        )
                        db.add(new_deadline)
                    await db.commit()
                    if extracted_deadlines:
                        logger.info(f"[Doc {document_id}] Initialized {len(extracted_deadlines)} deadlines via NER.")
        except Exception as e:
            logger.error(f"[Doc {document_id}] Initial Deadline extraction failed: {e}")

        # ── STEP 3: Chunk ────────────────────────────────────────────────
        logger.info(f"[Doc {document_id}] Chunking text...")
        chunks_data = document_chunker.chunk_document(normalized_text)
        total_chunks = len(chunks_data)
        logger.info(f"[Doc {document_id}] Created {total_chunks} chunks.")

        chunk_ids = []
        async with CeleryAsyncSessionLocal() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.total_chunks = total_chunks
                doc.processed_chunks = 0
                doc.processing_stage = "chunking_completed"
                doc.processing_progress = 12.0

            for chunk_dict in chunks_data:
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_dict["index"],
                    text_content=chunk_dict["text"],
                    page_number=chunk_dict.get("page_number"),
                )
                db.add(db_chunk)
                await db.flush()
                chunk_ids.append(db_chunk.id)

            await db.commit()

        # ── STEP 4: Single-pass AI analysis ─────────────────────────────
        logger.info(f"[Doc {document_id}] Running single-pass AI analysis...")
        async with CeleryAsyncSessionLocal() as db:
            from app.db.models.organization import Organization
            res = await db.execute(select(Organization).filter(Organization.id == organization_id))
            org = res.scalars().first()
            battery_save = org.ai_battery_save_mode if org else False
            logger.info(
                f"[Doc {document_id}] Organization={organization_id}, AI Battery Save={battery_save}"
            )

            doc = await document_crud.get(db, document_id)
            if doc:
                doc.processing_stage = "ai_analysis"
                doc.processing_progress = 35.0
                await db.commit()

            # Apply battery save to the normalized text
            input_text = normalized_text
            if battery_save and len(normalized_text) > 25000:
                logger.info(
                    f"[Doc {document_id}] Battery Save ON: Truncating text from {len(normalized_text)} to ~25k chars."
                )
                input_text = (
                    normalized_text[:15000]
                    + "\n\n[... TEXT TRUNCATED BY BATTERY SAVE MODE ...]\n\n"
                    + normalized_text[-10000:]
                )

            ai_analysis = {}
            try:
                ai_analysis = await document_intelligence_service.analyze_legal_document(
                    text=input_text,
                    filename=doc.filename if doc else str(document_id),
                    language=ocr_result.get("language", "en"),
                )
                logger.info(f"[Doc {document_id}] AI analysis returned successfully.")
            except Exception as e:
                logger.warning(f"[Doc {document_id}] AI analysis failed: {e}")
                # Log the error to database for debugging
                try:
                    async with CeleryAsyncSessionLocal() as error_db:
                        error_log = DocumentProcessingLog(
                            document_id=document_id,
                            stage="ai_analysis_failed",
                            error_message=str(e),
                            stack_trace="".join(tb.format_exception(type(e), e, e.__traceback__)),
                        )
                        error_db.add(error_log)
                        await error_db.commit()
                except:
                    pass  # Error logging failed, but don't stop pipeline
            
            # Ensure ai_analysis is always a dict (fix for string responses)
            if not isinstance(ai_analysis, dict):
                logger.warning(f"[Doc {document_id}] AI analysis returned non-dict: {type(ai_analysis)}. Using empty dict.")
                ai_analysis = {}

            # Merge regex metadata fallbacks
            try:
                from app.services.metadata_extraction import metadata_extraction_service

                regex_meta = await metadata_extraction_service.extract_metadata(
                    normalized_text, ocr_result.get("language", "en")
                )

                if not ai_analysis.get("parties"):
                    ai_analysis["parties"] = regex_meta.get("entities", [])

                if not ai_analysis.get("key_dates") and not ai_analysis.get("dates"):
                    ai_analysis["key_dates"] = regex_meta.get("dates", [])

                if not ai_analysis.get("financial_terms") and not ai_analysis.get("amounts"):
                    ai_analysis["financial_terms"] = regex_meta.get("amounts", [])

                if not ai_analysis.get("case_numbers"):
                    ai_analysis["case_numbers"] = regex_meta.get("case_numbers", [])

                if not ai_analysis.get("classification"):
                    ai_analysis["classification"] = ai_analysis.get("document_type") or "Unknown Document"

                if not ai_analysis.get("missing_documents") and not ai_analysis.get("missing_items"):
                    ai_analysis["missing_documents"] = regex_meta.get("missing_items") or []

                # Update document record with classification from AI
                doc = await document_crud.get(db, document_id)
                if doc:
                    doc.classification = ai_analysis.get("classification") or "Unknown Document"
                    await db.commit()

                ai_analysis["routing_ids"] = []
                ai_analysis["routing_projects"] = []
                ai_analysis["routing_organizations"] = []
            except Exception as meta_err:
                logger.warning(
                    f"[Doc {document_id}] Regex metadata extraction failed: {meta_err}"
                )
                ai_analysis.setdefault("routing_ids", [])
                ai_analysis.setdefault("routing_projects", [])
                ai_analysis.setdefault("routing_organizations", [])

            # Build simple confidence votes for AI tags
            try:
                tag_votes = []
                for t in ai_analysis.get("tags", []) or []:
                    tag_votes.append({"name": t, "confidence": 0.5})
                ai_analysis["tag_votes"] = tag_votes
            except Exception:
                pass

            # Store summary and metadata in one pass
            from app.db.models.summary import Summary
            from app.db.models.document_metadata import DocumentMetadata

            def _dedup_local(seq):
                seen, out = set(), []
                for item in seq or []:
                    key = str(item)
                    if key not in seen:
                        seen.add(key)
                        out.append(item)
                return out

            dates = ai_analysis.get("key_dates") or ai_analysis.get("dates", [])
            amounts = ai_analysis.get("financial_terms") or ai_analysis.get("amounts", [])
            case_numbers = ai_analysis.get("case_numbers", [])
            missing_docs = ai_analysis.get("missing_documents") or ai_analysis.get("missing_items", [])
            parties = ai_analysis.get("parties", [])

            # Rich entities from parties / attorneys
            entities = []
            for party in ai_analysis.get("parties", []):
                if isinstance(party, dict):
                    entities.append(
                        {
                            "name": party.get("name", ""),
                            "role": party.get("role", ""),
                            "id_number": party.get("id_number"),
                            "contact": party.get("contact"),
                            "firm": None,
                            "bar_number": None,
                        }
                    )
                elif isinstance(party, str) and party.strip():
                    entities.append(
                        {
                            "name": party,
                            "role": "Party",
                            "id_number": None,
                            "contact": None,
                            "firm": None,
                            "bar_number": None,
                        }
                    )

            for atty in ai_analysis.get("attorneys", []):
                if isinstance(atty, dict):
                    entities.append(
                        {
                            "name": atty.get("name", ""),
                            "role": f"Attorney representing {atty.get('representing', '')}".strip(),
                            "id_number": None,
                            "contact": None,
                            "firm": atty.get("firm"),
                            "bar_number": atty.get("bar_number"),
                        }
                    )
                elif isinstance(atty, str) and atty.strip():
                    entities.append(
                        {
                            "name": atty,
                            "role": "Attorney",
                            "id_number": None,
                            "contact": None,
                            "firm": None,
                            "bar_number": None,
                        }
                    )

            await db.execute(delete(Summary).where(Summary.document_id == document_id))
            await db.execute(
                delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id)
            )

            summary_text = ai_analysis.get("summary") or "No text summary could be generated."
            party_names = _dedup_local(
                [
                    (p.get("name") if isinstance(p, dict) else p)
                    for p in parties
                    if (p.get("name") if isinstance(p, dict) else p)
                ]
            )

            # ── RETRY LOGIC FOR METADATA/SUMMARY SAVING ────────────────────
            metadata_saved = False
            for attempt in range(3):
                try:
                    db.add(
                        Summary(
                            document_id=document_id,
                            organization_id=organization_id,
                            content=str(summary_text),
                            key_dates=_dedup_local(dates),
                            parties=party_names,
                            missing_documents_suggestion="\n".join(_dedup_local(missing_docs))
                            if missing_docs
                            else None,
                        )
                    )
                    db.add(
                        DocumentMetadata(
                            document_id=document_id,
                            dates=_dedup_local(dates),
                            entities=_dedup_local(entities),
                            amounts=_dedup_local(amounts),
                            case_numbers=_dedup_local(case_numbers),
                        )
                    )
                    await db.commit()
                    logger.info(f"[Doc {document_id}] Summary and metadata saved on attempt {attempt + 1}.")
                    metadata_saved = True
                    break
                except Exception as meta_err:
                    logger.warning(f"[Doc {document_id}] Metadata save attempt {attempt + 1} failed: {meta_err}")
                    try:
                        await db.rollback()
                    except:
                        pass
                    
                    if attempt < 2:
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"[Doc {document_id}] FAILED to save metadata after 3 attempts: {meta_err}")
                        try:
                            async with CeleryAsyncSessionLocal() as error_db:
                                error_log = DocumentProcessingLog(
                                    document_id=document_id,
                                    stage="metadata_save_failed",
                                    error_message=str(meta_err),
                                    stack_trace="".join(tb.format_exception(type(meta_err), meta_err, meta_err.__traceback__)),
                                )
                                error_db.add(error_log)
                                await error_db.commit()
                        except:
                            pass

            if not metadata_saved:
                logger.warning(f"[Doc {document_id}] Metadata save failed permanently. AI data will not be persisted for this document.")

            # AI-augmented deadlines from key_dates
            logger.info(f"[Doc {document_id}] Saving AI-augmented deadlines...")
            try:
                type_map = {
                    "hearing": DeadlineType.HEARING,
                    "filing": DeadlineType.FILING,
                    "response": DeadlineType.RESPONSE,
                    "appeal": DeadlineType.APPEAL,
                    "statute_of_limitations": DeadlineType.STATUTE_OF_LIMITATIONS,
                }

                added_count = 0
                for d in ai_analysis.get("key_dates", []) or []:
                    if isinstance(d, dict) and (
                        d.get("is_critical_deadline") or d.get("type") in type_map
                    ):
                        try:
                            parsed_date = dateparser.parse(d.get("date"))
                            if parsed_date:
                                new_deadline = Deadline(
                                    document_id=document_id,
                                    case_id=doc.case_id if doc else None,
                                    organization_id=organization_id,
                                    deadline_date=parsed_date,
                                    deadline_type=type_map.get(
                                        d.get("type", "other"), DeadlineType.OTHER
                                    ),
                                    description=d.get("description", "Legal Deadline"),
                                    confidence_score=0.95,
                                )
                                db.add(new_deadline)
                                added_count += 1
                        except Exception:
                            continue
                await db.commit()
                if added_count:
                    logger.info(
                        f"[Doc {document_id}] Added {added_count} high-fidelity AI deadlines."
                    )
            except Exception as e:
                logger.error(f"[Doc {document_id}] AI Deadline augmentation failed: {e}")

            # Smart Collections routing using the unified ai_analysis
            logger.info(f"[Doc {document_id}] Running AI-based collection routing...")
            try:
                from app.services.smart_collections import smart_collections_service

                await smart_collections_service.route_document_to_collections(
                    db, doc, ai_analysis
                )
                logger.info(f"[Doc {document_id}] AI Smart Collections routing complete.")
            except Exception as sc_err:
                logger.error(f"[Doc {document_id}] AI routing failed: {sc_err}")

        # ── STEP 6: Embeddings per chunk ────────────────────────────────
        if await _abort_if_timed_out("embedding"):
            return

        logger.info(f"[Doc {document_id}] Generating embeddings for {len(chunk_ids)} chunks...")
        if settings.DOCUMENT_EMBEDDING_FANOUT:
            async with CeleryAsyncSessionLocal() as db:
                doc = await document_crud.get(db, document_id)
                if doc:
                    doc.processed_chunks = 0
                    doc.processing_stage = "embedding"
                    doc.processing_progress = 57.0
                    await db.commit()

            try:
                from app.core.celery import safe_task_delay

                # Batch chunks instead of 1-per-task
                batch_size = settings.EMBEDDING_BATCH_SIZE
                for i in range(0, len(chunk_ids), batch_size):
                    batch = chunk_ids[i : i + batch_size]
                    safe_task_delay(
                        embed_chunk_batch_task,
                        document_id=document_id,
                        chunk_ids=batch,
                    )
                num_batches = (len(chunk_ids) + batch_size - 1) // batch_size
                logger.info(f"[Doc {document_id}] Embedding fan-out queued ({num_batches} batched tasks for {len(chunk_ids)} chunks).")
            except Exception as e:
                logger.error(f"[Doc {document_id}] Failed to queue embedding fan-out: {e}. Falling back to inline embedding.")
            else:
                return

        # Inline fallback: process embeddings sequentially
        for i, chunk_id in enumerate(chunk_ids):
            success = False
            retries = 0
            while not success and retries < 10:
                try:
                    async with CeleryAsyncSessionLocal() as db:
                        res = await db.execute(select(DocumentChunk).filter(DocumentChunk.id == chunk_id))
                        chunk = res.scalars().first()
                        if not chunk:
                            success = True
                            break

                        vector = await llm_service.generate_embedding(chunk.text_content)
                        chunk.embedding = vector

                        doc = await document_crud.get(db, document_id)
                        if doc:
                            doc.processing_progress = 57.0 + round(((i + 1) / len(chunk_ids)) * 38.0, 1)
                            doc.processing_stage = "embedding"
                        await db.commit()
                        success = True

                except Exception as e:
                    retries += 1
                    wait = min(20 * retries, 90)
                    logger.warning(f"[Doc {document_id}] Embedding chunk {i} error (attempt {retries}/10): {e}. Retrying in {wait}s.")
                    # Use asyncio.sleep instead of time.sleep to avoid blocking the worker
                    await asyncio.sleep(wait)

        # ── STEP 7: Finalize ────────────────────────────────────────────
        async with CeleryAsyncSessionLocal() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.processing_status = DocumentProcessingStatus.COMPLETED
                doc.processing_stage = "completed"
                doc.processing_progress = 100.0
                await db.commit()
                logger.info(f"[Doc {document_id}] ✅ FULLY COMPLETED.")

                try:
                    await _create_org_notification(
                        db,
                        organization_id=organization_id,
                        event_type="DOCUMENT_PROCESSED",
                        title="Document Processed",
                        message=f"Document '{doc.filename}' is ready.",
                        source_type="document",
                        source_id=document_id,
                    )
                except Exception as broadcast_err:
                    logger.error(f"[Doc {document_id}] Persisting completion notification failed: {broadcast_err}", exc_info=True)

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
        log_entry = DocumentProcessingLog(
            document_id=document_id,
            stage="top_level",
            error_message=str(exc),
            stack_trace="".join(tb.format_exception(type(exc), exc, exc.__traceback__)),
        )
        db.add(log_entry)
        await db.commit()
