"""Unified document processing pipeline (Celery + BackgroundTasks)."""
from __future__ import annotations

import asyncio
import logging
import time
import traceback as tb
from typing import Callable, Optional

import dateparser
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.crud.document import document_crud
from app.db.models.deadline import Deadline, DeadlineType
from app.db.models.document import Document, DocumentChunk, DocumentProcessingStatus
from app.db.models.document_metadata import DocumentMetadata
from app.db.models.summary import Summary
from app.db.models.organization import Organization
from app.services.ai.ner_service import ner_service
from app.services.ai_utils import valid_embedding
from app.services.collections_analysis import classification_from_analysis
from app.services.document_chunker import document_chunker
from app.services.document_intelligence import document_intelligence_service
from app.services.document_notifications import create_org_notification
from app.services.processing_telemetry import track_stage, record_processing_error, emit_stage
from app.services.llm import llm_service
from app.services.ocr import ocr_service
from app.services.text_normalization import text_normalization_service

logger = logging.getLogger(__name__)


def _set_ai_health(doc: Document, **fields) -> None:
    health = dict(doc.ai_health or {})
    health.update(fields)
    doc.ai_health = health


async def run_document_pipeline(
    document_id: int,
    file_path: str,
    user_id: int,
    organization_id: int,
    *,
    session_factory,
    allow_embed_fanout: bool = True,
    queue_embed_batch: Optional[Callable[[int, list[int]], None]] = None,
) -> None:
    start_time = time.time()

    async def _abort_if_timed_out(stage: str) -> bool:
        max_seconds = settings.DOCUMENT_MAX_PROCESSING_SECONDS or 0
        if max_seconds <= 0:
            return False
        if (time.time() - start_time) <= max_seconds:
            return False
        async with session_factory() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.processing_status = DocumentProcessingStatus.COMPLETED
                doc.processing_stage = "completed_without_ai"
                doc.processing_progress = 100.0
                doc.classification = "Text Extracted (AI Pending)"
                _set_ai_health(doc, analysis="skipped", embedding="skipped")
                await db.commit()
        logger.warning("[Doc %d] Processing timed out at stage=%s. Marked completed_without_ai.", document_id, stage)
        return True

    # ── STEP 1: Update status to PROCESSING ─────────────────────────
    async with session_factory() as db:
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
        async with track_stage(document_id, organization_id, "ocr"):
            logger.info(f"[Doc {document_id}] Running OCR on {file_path}...")
            ocr_result = await ocr_service.extract_text_from_file(file_path)
            extracted_text = ocr_result.get("text", "") or ""
            normalized_text = text_normalization_service.normalize(
                extracted_text, language=ocr_result.get("language", "en")
            )
    except Exception as e:
        logger.error(f"[Doc {document_id}] OCR FAILED: {e}")
        async with session_factory() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.processing_status = DocumentProcessingStatus.FAILED
                doc.processing_stage = "ocr_failed"
                await db.commit()
            try:
                await record_processing_error(
                    db,
                    document_id=document_id,
                    organization_id=organization_id,
                    stage="ocr_failed",
                    error=e,
                )
            except Exception:
                pass
        return

    async with session_factory() as db:
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
                await create_org_notification(
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
        
        async with session_factory() as db:
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
    async with track_stage(document_id, organization_id, "chunking"):
        logger.info(f"[Doc {document_id}] Chunking text...")
        chunks_data = document_chunker.chunk_document(normalized_text)
    total_chunks = len(chunks_data)
    logger.info(f"[Doc {document_id}] Created {total_chunks} chunks.")

    chunk_ids = []
    async with session_factory() as db:
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

    # ── STEP 4: AI analysis (single-pass or chunked map-reduce) ─────
    use_chunked = document_intelligence_service.should_use_chunked_analysis(
        len(normalized_text)
    )
    logger.info(
        f"[Doc {document_id}] Running AI analysis (mode={'chunked' if use_chunked else 'full'})..."
    )
    async with session_factory() as db:
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

        input_text = normalized_text
        if battery_save and not use_chunked and len(normalized_text) > 25000:
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
            async with track_stage(
                document_id,
                organization_id,
                "ai_analysis",
                analysis_mode="chunked" if use_chunked else "full",
            ):
                ai_analysis = await document_intelligence_service.analyze_document(
                    text=input_text,
                    filename=doc.filename if doc else str(document_id),
                    language=ocr_result.get("language", "en"),
                    chunks=chunks_data if use_chunked else None,
                    document_id=document_id,
                    organization_id=organization_id,
                )
            logger.info(f"[Doc {document_id}] AI analysis returned successfully.")

            chunk_partials = ai_analysis.pop("_chunk_partials", None) or []
            if chunk_partials and chunk_ids:
                for chunk_id, partial in zip(chunk_ids, chunk_partials):
                    res = await db.execute(
                        select(DocumentChunk).filter(DocumentChunk.id == chunk_id)
                    )
                    db_chunk = res.scalars().first()
                    if db_chunk:
                        store = dict(partial)
                        store.pop("_chunk_index", None)
                        db_chunk.chunk_analysis = store
                await db.commit()
                logger.info(
                    f"[Doc {document_id}] Stored chunk_analysis on {len(chunk_partials)} chunks."
                )
        except Exception as e:
            logger.warning(f"[Doc {document_id}] AI analysis failed: {e}")
            try:
                async with session_factory() as error_db:
                    await record_processing_error(
                        error_db,
                        document_id=document_id,
                        organization_id=organization_id,
                        stage="ai_analysis_failed",
                        error=e,
                    )
            except Exception:
                pass
        
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

            # Note: regex extractor doesn't currently detect "missing items"; keep AI value if present.
            if not ai_analysis.get("missing_documents") and ai_analysis.get("missing_items"):
                ai_analysis["missing_documents"] = ai_analysis.get("missing_items") or []

            doc = await document_crud.get(db, document_id)
            if doc:
                doc.classification = classification_from_analysis(ai_analysis)
                mode = ai_analysis.get("analysis_mode") or ("chunked" if use_chunked else "full")
                _set_ai_health(
                    doc,
                    analysis="ok" if ai_analysis else "partial",
                    analysis_mode=mode,
                    chunks_analyzed=ai_analysis.get("chunks_analyzed"),
                )
                await db.commit()

            # IMPORTANT: keep routing_* extracted by regex so Smart Collections can work
            # even when the AI response is sparse.
            ai_analysis["routing_ids"] = regex_meta.get("routing_ids", []) or []
            ai_analysis["routing_projects"] = regex_meta.get("routing_projects", []) or []
            ai_analysis["routing_organizations"] = regex_meta.get("routing_organizations", []) or []
        except Exception as meta_err:
            logger.warning(
                f"[Doc {document_id}] Regex metadata extraction failed: {meta_err}"
            )
            ai_analysis.setdefault("routing_ids", [])
            ai_analysis.setdefault("routing_projects", [])
            ai_analysis.setdefault("routing_organizations", [])

        # Build simple confidence votes for AI tags
        try:
            # Normalize tags into a list of strings (providers sometimes return a single string)
            raw_tags = ai_analysis.get("tags")
            if isinstance(raw_tags, str):
                # Split on commas/newlines; keep non-empty tokens
                ai_analysis["tags"] = [t.strip() for t in raw_tags.replace("\n", ",").split(",") if t.strip()]
            elif raw_tags is None:
                ai_analysis["tags"] = []

            tag_votes = []
            for t in ai_analysis.get("tags", []) or []:
                # When the LLM already produced a "tags" list but didn't provide
                # confidences, assume they are relevant enough to pass filtering.
                tag_votes.append({"name": t, "confidence": 0.8})
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

        # If the structured AI response omitted/emptied the summary, generate one with the
        # simpler summarizer as a fallback.
        summary_text = ai_analysis.get("summary")
        if not isinstance(summary_text, str) or not summary_text.strip():
            try:
                summary_text = await asyncio.wait_for(
                    llm_service.summarize_text(
                        input_text if isinstance(input_text, str) and input_text.strip() else normalized_text
                    ),
                    timeout=float(settings.AI_ANALYSIS_TIMEOUT_SECONDS or 120),
                )
            except Exception:
                summary_text = None
        if not isinstance(summary_text, str) or not summary_text.strip():
            summary_text = "Summary unavailable."
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
                        async with session_factory() as error_db:
                            await record_processing_error(
                                error_db,
                                document_id=document_id,
                                organization_id=organization_id,
                                stage="metadata_save_failed",
                                error=meta_err,
                            )
                    except Exception:
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
            logger.error(f"[Doc {document_id}] AI routing failed: {sc_err}", exc_info=True)

    # ── STEP 6: Embeddings per chunk ────────────────────────────────
    if await _abort_if_timed_out("embedding"):
        return

    logger.info(f"[Doc {document_id}] Generating embeddings for {len(chunk_ids)} chunks...")
    use_fanout = (
        allow_embed_fanout
        and settings.DOCUMENT_EMBEDDING_FANOUT
        and chunk_ids
    )
    if use_fanout:
        async with session_factory() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.processed_chunks = 0
                doc.embedding_failed_count = 0
                doc.processing_stage = "embedding"
                doc.processing_progress = 57.0
                _set_ai_health(doc, embedding="in_progress")
                await db.commit()

        try:
            batch_size = settings.EMBEDDING_BATCH_SIZE
            for i in range(0, len(chunk_ids), batch_size):
                batch = chunk_ids[i : i + batch_size]
                if queue_embed_batch:
                    queue_embed_batch(document_id, batch)
                else:
                    from app.core.celery import safe_task_delay
                    from app.workers.document_tasks import embed_chunk_batch_task

                    safe_task_delay(
                        embed_chunk_batch_task,
                        document_id=document_id,
                        chunk_ids=batch,
                    )
            num_batches = (len(chunk_ids) + batch_size - 1) // batch_size
            logger.info(
                f"[Doc {document_id}] Embedding fan-out queued ({num_batches} batches)."
            )
        except Exception as e:
            logger.error(
                f"[Doc {document_id}] Failed to queue embedding fan-out: {e}. Falling back to inline."
            )
        else:
            emit_stage(
                document_id=document_id,
                organization_id=organization_id,
                stage="pipeline_total",
                duration_ms=int((time.time() - start_time) * 1000),
                status="ok",
                embedding_mode="celery_fanout",
            )
            return

    async with track_stage(
        document_id,
        organization_id,
        "embedding_inline",
        chunk_count=len(chunk_ids),
    ):
        await _embed_chunks_inline(
            document_id,
            organization_id,
            chunk_ids,
            session_factory,
        )

    emit_stage(
        document_id=document_id,
        organization_id=organization_id,
        stage="pipeline_total",
        duration_ms=int((time.time() - start_time) * 1000),
        status="ok",
    )


async def _embed_chunks_inline(
    document_id: int,
    organization_id: int,
    chunk_ids: list[int],
    session_factory,
) -> None:
    for i, chunk_id in enumerate(chunk_ids):
        success = False
        retries = 0
        while not success and retries < 10:
            try:
                async with session_factory() as db:
                    res = await db.execute(select(DocumentChunk).filter(DocumentChunk.id == chunk_id))
                    chunk = res.scalars().first()
                    if not chunk:
                        success = True
                        break

                    vector = await llm_service.generate_embedding(chunk.text_content)
                    doc = await document_crud.get(db, document_id)
                    if not valid_embedding(vector):
                        if doc:
                            doc.embedding_failed_count = (doc.embedding_failed_count or 0) + 1
                        await db.commit()
                        success = True
                        break
                    chunk.embedding = vector
                    if doc:
                        doc.processing_progress = 57.0 + round(
                            ((i + 1) / len(chunk_ids)) * 38.0, 1
                        )
                        doc.processing_stage = "embedding"
                    await db.commit()
                    success = True

            except Exception as e:
                retries += 1
                wait = min(20 * retries, 90)
                logger.warning(f"[Doc {document_id}] Embedding chunk {i} error (attempt {retries}/10): {e}. Retrying in {wait}s.")
                # Use asyncio.sleep instead of time.sleep to avoid blocking the worker
                await asyncio.sleep(wait)

    await _finalize_document(
        document_id, organization_id, session_factory, start_time=None
    )


async def _finalize_document(
    document_id: int,
    organization_id: int,
    session_factory,
    *,
    start_time: float | None = None,
) -> None:
    # ── Finalize ────────────────────────────────────────────
    async with session_factory() as db:
        doc = await document_crud.get(db, document_id)
        if doc:
            failed = doc.embedding_failed_count or 0
            doc.processing_status = DocumentProcessingStatus.COMPLETED
            if failed > 0:
                doc.processing_stage = "completed_embedding_partial"
                _set_ai_health(doc, embedding="partial")
            else:
                doc.processing_stage = "completed"
                _set_ai_health(doc, embedding="ok")
            doc.processing_progress = 100.0
            await db.commit()
            logger.info(f"[Doc {document_id}] ✅ FULLY COMPLETED (stage={doc.processing_stage}).")

            try:
                await create_org_notification(
                    db,
                    organization_id=organization_id,
                    event_type="DOCUMENT_PROCESSED",
                    title="Document Processed",
                    message=f"Document '{doc.filename}' is ready.",
                    source_type="document",
                    source_id=document_id,
                )
            except Exception as broadcast_err:
                logger.error(
                    f"[Doc {document_id}] Persisting completion notification failed: {broadcast_err}",
                    exc_info=True,
                )
