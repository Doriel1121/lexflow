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
"""

import asyncio
import logging
import time
from celery import shared_task
from app.db.session import CeleryAsyncSessionLocal
from app.crud.document import document_crud
from app.db.models.document import DocumentProcessingStatus, DocumentChunk
from app.services.ocr import ocr_service
from app.services.document_chunker import document_chunker
from app.services.ai.ner_service import ner_service
from app.db.models.deadline import Deadline, DeadlineType
import dateparser
from app.services.document_intelligence import document_intelligence_service
from app.services.llm import llm_service
from app.api.ws.notifications import notification_manager
from sqlalchemy import select, delete

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine inside a synchronous Celery task."""
    return asyncio.run(coro)


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def process_document_pipeline(self, document_id: int, file_path: str, user_id: int, organization_id: int):
    """
    Entry point for the document processing pipeline (called by upload API).
    Runs the complete pipeline in a single sequential task.
    """
    logger.info(f"[Doc {document_id}] Pipeline started. file_path={file_path}")

    async def _run():
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
            extracted_text = ocr_result.get("text", "")
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
                doc.content = extracted_text
                doc.language = ocr_result.get("language", "en")
                doc.page_count = ocr_result.get("page_count", 0)
                doc.processing_stage = "ocr_completed"
                doc.processing_progress = 8.0
                await db.commit()
                logger.info(f"[Doc {document_id}] OCR done: {len(extracted_text)} chars, {doc.page_count} pages.")

                # Notify UI that OCR text is ready for viewing
                try:
                    await notification_manager.broadcast_to_organization(
                        organization_id,
                        {
                            "type": "DOCUMENT_STATUS_UPDATE",
                            "document_id": document_id,
                            "status": "processing",
                            "stage": "ocr_completed",
                            "progress": 8.0,
                            "message": "Text extraction complete. Document is now viewable."
                        }
                    )
                except Exception:
                    pass

        # ── STEP 2.5: Deadline Extraction ─────────────────────────────
        logger.info(f"[Doc {document_id}] Extracting deadlines...")
        try:
            # We take all NER results here as initial candidates
            extracted_deadlines = ner_service.extract_deadlines(extracted_text, language=ocr_result.get("language", "en"))
            
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
        chunks_data = document_chunker.chunk_document(extracted_text)
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
                    text_content=chunk_dict["text"]
                )
                db.add(db_chunk)
                await db.flush()
                chunk_ids.append(db_chunk.id)

            await db.commit()

        # ── STEP 4: AI Analysis per chunk ───────────────────────────────
        logger.info(f"[Doc {document_id}] Starting AI analysis for {total_chunks} chunks...")
        ai_analysis_failed = False
        consecutive_quota_failures = 0
        start_time = time.time()
        # Hard timeout for AI phase: 15 minutes
        MAX_AI_PHASE_DURATION = 900 
        
        # Fetch Battery Save setting
        async with CeleryAsyncSessionLocal() as db:
            from app.db.models.organization import Organization
            res = await db.execute(select(Organization).filter(Organization.id == organization_id))
            org = res.scalars().first()
            battery_save = org.ai_battery_save_mode if org else False
            logger.info(f"[Doc {document_id}] Pipeline Start. Organization: {organization_id}, AI Battery Save: {battery_save}")

        chunks_to_process = []
        if not battery_save:
            # Process ALL chunks if battery save is OFF
            chunks_to_process = list(enumerate(chunk_ids))
        else:
            # Optimization: If battery save is ON, only analyze a sample
            logger.info(f"[Doc {document_id}] AI Battery Save Mode is ON. Sampling chunks.")
            max_chunks_to_analyze = 8
            if total_chunks <= max_chunks_to_analyze:
                chunks_to_process = list(enumerate(chunk_ids))
            else:
                chunks_to_process.extend(list(enumerate(chunk_ids))[:4])
                chunks_to_process.extend(list(enumerate(chunk_ids))[-2:])
                mid = total_chunks // 2
                chunks_to_process.append((mid, chunk_ids[mid]))
                chunks_to_process.append((mid + 1, chunk_ids[mid + 1]))
                chunks_to_process = sorted(list(set(chunks_to_process)))

        for i, chunk_id in chunks_to_process:
            # Check for hard timeout
            if time.time() - start_time > MAX_AI_PHASE_DURATION:
                logger.error(f"[Doc {document_id}] AI analysis reached hard timeout (15m). Aborting AI phase.")
                ai_analysis_failed = True
                break

            if consecutive_quota_failures >= 3:
                logger.error(f"[Doc {document_id}] Circuit Breaker: Too many quota failures. Aborting AI phase.")
                ai_analysis_failed = True
                break

            success = False
            retries = 0
            # Reduced internal retries because ai_provider now handles it globally
            while not success and retries < 3:
                try:
                    async with CeleryAsyncSessionLocal() as db:
                        res = await db.execute(select(DocumentChunk).filter(DocumentChunk.id == chunk_id))
                        chunk = res.scalars().first()
                        if not chunk:
                            success = True
                            break

                        analysis = await document_intelligence_service.analyze_legal_document(
                            text=chunk.text_content,
                            filename=f"{document_id}_chunk_{i}"
                        )
                        chunk.chunk_analysis = analysis

                        doc = await document_crud.get(db, document_id)
                        if doc:
                            # Update progress based on total chunks to analyze
                            doc.processed_chunks = i + 1
                            doc.processing_progress = 12.0 + round(((chunks_to_process.index((i, chunk_id)) + 1) / len(chunks_to_process)) * 43.0, 1)
                            doc.processing_stage = "ai_analysis"
                        await db.commit()
                        success = True
                        consecutive_quota_failures = 0 # Reset on success
                        logger.info(f"[Doc {document_id}] AI analysis: chunk {i+1}/{total_chunks} done.")
                        
                        # Mandatory delay to respect rate limits (2s)
                        await asyncio.sleep(2)

                except Exception as e:
                    retries += 1
                    err_msg = str(e).lower()
                    if "quota" in err_msg or "429" in err_msg:
                        consecutive_quota_failures += 1
                        # Global retry handles it, but if it still fails, we wait longer here
                        await asyncio.sleep(15 * retries)
                    else:
                        logger.warning(f"[Doc {document_id}] Chunk {i} AI error: {e}. Retry {retries}/3.")

        # If AI analysis failed due to quota, mark as partially completed
        if ai_analysis_failed:
            logger.warning(f"[Doc {document_id}] AI analysis failed due to quota. Marking as PARTIALLY_COMPLETED.")
            async with CeleryAsyncSessionLocal() as db:
                doc = await document_crud.get(db, document_id)
                if doc:
                    doc.processing_status = DocumentProcessingStatus.COMPLETED
                    doc.processing_stage = "completed_without_ai"
                    doc.processing_progress = 100.0
                    doc.classification = "Text Extracted (AI Pending)"
                    await db.commit()
                    logger.info(f"[Doc {document_id}] ✅ COMPLETED WITHOUT AI ANALYSIS (quota exceeded).")
            return  # Exit early, skip aggregation and embeddings

        # ── STEP 5: Aggregate (Reduce) ───────────────────────────────────
        logger.info(f"[Doc {document_id}] Aggregating analysis results...")
        async with CeleryAsyncSessionLocal() as db:
            doc = await document_crud.get(db, document_id)
            if doc:
                doc.processing_stage = "aggregating"
                doc.processing_progress = 57.0
                await db.commit()

            res = await db.execute(select(DocumentChunk).filter(DocumentChunk.document_id == document_id))
            chunks = res.scalars().all()

            all_summaries, all_key_dates, all_parties = [], [], []
            all_missing, all_amounts, all_case_numbers = [], [], []
            all_tags: set = set()
            doc_type, doc_subtype = None, None
            # Rich entity list — always dicts for consistent UI rendering
            all_entities: list = []

            for c in chunks:
                if not c.chunk_analysis or not isinstance(c.chunk_analysis, dict):
                    continue
                ana = c.chunk_analysis
                if ana.get("summary") and "chunk_" not in str(ana.get("summary", "")):
                    all_summaries.append(ana["summary"])
                if ana.get("key_dates"): all_key_dates.extend(ana["key_dates"])
                if ana.get("parties"): all_parties.extend(ana["parties"])
                if ana.get("missing_items"): all_missing.extend(ana["missing_items"])
                if ana.get("financial_terms"): all_amounts.extend(ana["financial_terms"])
                if ana.get("case_numbers"): all_case_numbers.extend(ana["case_numbers"])
                if ana.get("tags"): all_tags.update(ana["tags"])
                
                # Use first non-empty document type/subtype found in chunks
                if not doc_type and ana.get("document_type"):
                    doc_type = ana["document_type"]
                if not doc_subtype and ana.get("document_subtype"):
                    doc_subtype = ana["document_subtype"]

                # Build rich entity dicts from parties
                for party in (ana.get("parties") or []):
                    if isinstance(party, dict):
                        all_entities.append({
                            "name": party.get("name", ""),
                            "role": party.get("role", ""),
                            "id_number": party.get("id_number"),
                            "contact": party.get("contact"),
                            "firm": None,
                            "bar_number": None,
                        })
                    elif isinstance(party, str) and party.strip():
                        all_entities.append({"name": party, "role": "Party",
                                            "id_number": None, "contact": None,
                                            "firm": None, "bar_number": None})

                # Build rich entity dicts from attorneys
                for atty in (ana.get("attorneys") or []):
                    if isinstance(atty, dict):
                        all_entities.append({
                            "name": atty.get("name", ""),
                            "role": f"Attorney representing {atty.get('representing', '')}".strip(),
                            "id_number": None,
                            "contact": None,
                            "firm": atty.get("firm"),
                            "bar_number": atty.get("bar_number"),
                        })
                    elif isinstance(atty, str) and atty.strip():
                        all_entities.append({"name": atty, "role": "Attorney",
                                            "id_number": None, "contact": None,
                                            "firm": None, "bar_number": None})

            def dedup(lst):
                seen, out = set(), []
                for d in lst:
                    key = str(d)
                    if key not in seen:
                        seen.add(key)
                        out.append(d)
                return out

            from app.db.models.summary import Summary
            from app.db.models.document_metadata import DocumentMetadata

            await db.execute(delete(Summary).where(Summary.document_id == document_id))
            await db.execute(delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id))

            # Party names as plain strings for legacy summary.parties field
            party_names = dedup([
                (p.get("name") if isinstance(p, dict) else p)
                for p in all_parties
                if (p.get("name") if isinstance(p, dict) else p)
            ])
            date_strs = dedup([
                (d.get("date") if isinstance(d, dict) else d)
                for d in all_key_dates
                if (d.get("date") if isinstance(d, dict) else d)
            ])

            summary_text = "\n\n".join(all_summaries)[:5000] if all_summaries else None
            db.add(Summary(
                document_id=document_id,
                organization_id=organization_id,
                content=summary_text or "Processing complete. No text summary could be generated.",
                key_dates=dedup(all_key_dates),
                parties=party_names,
                missing_documents_suggestion="\n".join(dedup(all_missing))
            ))
            db.add(DocumentMetadata(
                document_id=document_id,
                dates=dedup(all_key_dates),
                entities=dedup(all_entities),   # rich dicts — UI renders name/role/id_number
                amounts=dedup(all_amounts),
                case_numbers=dedup(all_case_numbers)
            ))
            await db.commit()
            logger.info(f"[Doc {document_id}] Summary and metadata saved.")

            # ── NEW: Augmented Deadline Extraction from AI results ──────────
            logger.info(f"[Doc {document_id}] Saving AI-augmented deadlines...")
            try:
                type_map = {
                    "hearing": DeadlineType.HEARING,
                    "filing": DeadlineType.FILING,
                    "response": DeadlineType.RESPONSE,
                    "appeal": DeadlineType.APPEAL,
                    "statute_of_limitations": DeadlineType.STATUTE_OF_LIMITATIONS
                }
                
                # Deduplicate and filter LLM dates
                added_count = 0
                for d in all_key_dates:
                    if isinstance(d, dict) and (d.get("is_critical_deadline") or d.get("type") in type_map):
                        try:
                            # Try to parse date from LLM string
                            parsed_date = dateparser.parse(d["date"])
                            if parsed_date:
                                new_deadline = Deadline(
                                    document_id=document_id,
                                    case_id=doc.case_id,
                                    organization_id=organization_id,
                                    deadline_date=parsed_date,
                                    deadline_type=type_map.get(d.get("type", "other"), DeadlineType.OTHER),
                                    description=d.get("description", "Legal Deadline"),
                                    confidence_score=0.95
                                )
                                db.add(new_deadline)
                                added_count += 1
                        except:
                            continue
                await db.commit()
                if added_count:
                    logger.info(f"[Doc {document_id}] Added {added_count} high-fidelity AI deadlines.")
            except Exception as e:
                logger.error(f"[Doc {document_id}] AI Deadline augmentation failed: {e}")

            # ── STEP 5.5: AI-based Collection Routing ───────────────────────
            logger.info(f"[Doc {document_id}] Running AI-based collection routing...")
            try:
                from app.services.smart_collections import smart_collections_service
                # Reconstruct an AI analysis dict for the routing service
                full_ai_analysis = {
                    "parties": dedup(all_parties),
                    "document_type": doc_type,
                    "document_subtype": doc_subtype,
                    "tags": list(all_tags),
                    "routing_ids": [], # We explicitly avoid regex here
                    "routing_projects": [],
                    "routing_organizations": []
                }
                await smart_collections_service.route_document_to_collections(
                    db, doc, full_ai_analysis
                )
                logger.info(f"[Doc {document_id}] AI Smart Collections routing complete.")
            except Exception as sc_err:
                logger.error(f"[Doc {document_id}] AI routing failed: {sc_err}")

        # ── STEP 6: Embeddings per chunk ────────────────────────────────
        logger.info(f"[Doc {document_id}] Generating embeddings for {len(chunk_ids)} chunks...")
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
                            # Embedding = 57% to 95%
                            doc.processing_progress = 57.0 + round(((i + 1) / len(chunk_ids)) * 38.0, 1)
                            doc.processing_stage = "embedding"
                        await db.commit()
                        success = True

                except Exception as e:
                    retries += 1
                    wait = min(20 * retries, 90)
                    logger.warning(f"[Doc {document_id}] Embedding chunk {i} error (attempt {retries}/10): {e}. Retrying in {wait}s.")
                    time.sleep(wait)

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
                    await notification_manager.broadcast_to_organization(
                        organization_id,
                        {
                            "type": "DOCUMENT_PROCESSED",
                            "document_id": document_id,
                            "message": f"Document '{doc.filename}' is ready."
                        }
                    )
                except Exception:
                    pass  # Don't fail on notification error

    run_async(_run())
