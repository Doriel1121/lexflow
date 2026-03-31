"""
Document Processing Service — FastAPI BackgroundTask implementation.

This is the primary processing path. It runs within the FastAPI worker
process as an async background task (no Celery/Redis required).

Pipeline stages and progress %:
  0% — uploaded / queued
  5% — processing started
  20% — OCR complete
  35% — AI analysis complete
  50% — metadata + summary saved
  65%–95% — embeddings (per chunk)
  100% — completed
"""

import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

import dateparser
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.document import document_crud
from app.crud.document_metadata import crud_document_metadata
from app.crud.summary import crud_summary
from app.crud.tag import crud_tag
from app.db.models.document import Document, DocumentChunk, DocumentProcessingStatus
from app.db.models.document_metadata import DocumentMetadata
from app.db.models.summary import Summary
from app.schemas.document_metadata import DocumentMetadataCreate
from app.schemas.summary import SummaryCreate
from app.schemas.tag import TagCreate
from app.services.audit import log_audit
from app.services.document_intelligence import document_intelligence_service
from app.services.llm import llm_service
from app.services.ocr import ocr_service
from app.services.text_normalization import text_normalization_service
from app.services.ai.ner_service import ner_service
from app.db.models.deadline import Deadline, DeadlineType
from app.services.smart_collections import smart_collections_service
from app.db.session import AsyncSessionLocal
from app.db.models.document_processing_log import DocumentProcessingLog
import traceback as tb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dedup(lst: list) -> list:
    """Deduplicate a list while preserving order."""
    seen, out = set(), []
    for item in lst:
        key = str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _extract_rich_entities(ai_analysis: Dict[str, Any]) -> List[Any]:
    """
    Build a unified entity list from AI analysis.
    Combines parties (with role, id_number, contact) and attorneys
    (with firm, bar_number) into a single list of rich dicts.
    Always returns dicts — never raw strings.
    """
    entities: List[Dict] = []

    for party in ai_analysis.get("parties", []):
        if isinstance(party, dict):
            entities.append({
                "name": party.get("name", ""),
                "role": party.get("role", ""),
                "id_number": party.get("id_number"),
                "contact": party.get("contact"),
                "firm": None,
                "bar_number": None,
            })
        elif isinstance(party, str) and party.strip():
            entities.append({"name": party, "role": "Party", "id_number": None,
                             "contact": None, "firm": None, "bar_number": None})

    for attorney in ai_analysis.get("attorneys", []):
        if isinstance(attorney, dict):
            entities.append({
                "name": attorney.get("name", ""),
                "role": f"Attorney representing {attorney.get('representing', '')}".strip(),
                "id_number": None,
                "contact": None,
                "firm": attorney.get("firm"),
                "bar_number": attorney.get("bar_number"),
            })
        elif isinstance(attorney, str) and attorney.strip():
            entities.append({"name": attorney, "role": "Attorney", "id_number": None,
                             "contact": None, "firm": None, "bar_number": None})

    return _dedup(entities)


async def _set_status(
    db: AsyncSession,
    document: Document,
    status: DocumentProcessingStatus,
    stage: str,
    progress: float,
):
    """Update and commit processing status on a document."""
    document.processing_status = status
    document.processing_stage = stage
    document.processing_progress = round(progress, 1)
    await db.commit()


# ---------------------------------------------------------------------------
# Main processing service
# ---------------------------------------------------------------------------

class DocumentProcessingService:

    async def process_document_background(
        self,
        document_id: int,
        file_path: str,
        user_id: int,
        organization_id: Optional[int],
    ):
        """
        Full async document processing pipeline executed as a FastAPI BackgroundTask.
        Creates its own AsyncSession locally to avoid cross-thread attached exceptions.
        """
        logger.info("[Doc %d] Background processing started. file=%s", document_id, file_path)

        async with AsyncSessionLocal() as db:
            # ── Load document ────────────────────────────────────────────────────
            document = await document_crud.get(db, document_id)
            if not document:
                logger.error("[Doc %d] Not found — aborting.", document_id)
                return

            try:
                start_time = time.time()

                async def _abort_if_timed_out(stage: str) -> bool:
                    max_seconds = settings.DOCUMENT_MAX_PROCESSING_SECONDS or 0
                    if max_seconds <= 0:
                        return False
                    if (time.time() - start_time) <= max_seconds:
                        return False
                    doc = await document_crud.get(db, document_id)
                    if doc:
                        doc.processing_status = DocumentProcessingStatus.COMPLETED
                        doc.processing_stage = "completed_without_ai"
                        doc.processing_progress = 100.0
                        doc.classification = "Text Extracted (AI Pending)"
                        await db.commit()
                    logger.warning("[Doc %d] Processing timed out at stage=%s. Marked completed_without_ai.", document_id, stage)
                    return True

                await _set_status(db, document, DocumentProcessingStatus.PROCESSING,
                                  "processing_started", 5.0)

                # ── STEP 1: OCR ──────────────────────────────────────────────────
                logger.info("[Doc %d] Running OCR on %s", document_id, file_path)
                try:
                    ocr_result = await ocr_service.extract_text_from_file(file_path)
                    extracted_text = ocr_result.get("text", "") or ""
                    normalized_text = text_normalization_service.normalize(
                        extracted_text, language=ocr_result.get("language", "en")
                    )
                    language = ocr_result.get("language", "en")
                    page_count = ocr_result.get("page_count", 0)
                except Exception as ocr_err:
                    logger.error("[Doc %d] OCR failed: %s", document_id, ocr_err)
                    extracted_text, normalized_text, language, page_count = "", "", "en", 0

                document = await document_crud.get(db, document_id)
                if not document:
                    return
                document.content = normalized_text
                document.language = language
                document.page_count = page_count
                document.processing_stage = "ocr_completed"
                document.processing_progress = 20.0
                await db.commit()
                logger.info("[Doc %d] OCR done: %d chars, %d pages. Marking as viewable.", document_id,
                            len(extracted_text), page_count)

                # Broadcast that text is ready
                try:
                    from app.api.ws.notifications import notification_manager
                    await notification_manager.broadcast_to_organization(
                        organization_id,
                        {
                            "type": "DOCUMENT_STATUS_UPDATE",
                            "document_id": document_id,
                            "status": "processing",
                            "stage": "ocr_completed",
                            "progress": 20.0
                        },
                    )
                except Exception:
                    pass

                if not extracted_text.strip():
                    await _set_status(db, document, DocumentProcessingStatus.FAILED,
                                      "ocr_empty_text", 20.0)
                    return

                if await _abort_if_timed_out("ocr_completed"):
                    return

                # Fetch Battery Save setting
                from app.db.models.organization import Organization
                org = await db.get(Organization, organization_id)
                battery_save = org.ai_battery_save_mode if org else False
                
                # ── STEP 2: AI parsing ───────────────────────────────────────────
                logger.info("[Doc %d] Submitting to AI for analysis. Battery Save: %s", document_id, battery_save)
                await _set_status(db, document, DocumentProcessingStatus.PROCESSING,
                                  "ai_analysis", 35.0)

                # If battery save is ON, optimize the input text to save tokens
                input_text = normalized_text
                if battery_save and len(normalized_text) > 25000:
                    logger.info("[Doc %d] Battery Save ON: Truncating text from %d to ~25k chars.", document_id, len(normalized_text))
                    # Keep first 15k and last 10k
                    input_text = normalized_text[:15000] + "\n\n[... TEXT TRUNCATED BY BATTERY SAVE MODE ...]\n\n" + normalized_text[-10000:]

                ai_analysis: Dict[str, Any] = {}
                try:
                    ai_analysis = await document_intelligence_service.analyze_legal_document(
                        input_text,
                        filename=document.filename,
                        language=language,
                    )
                    logger.info("[Doc %d] AI analysis returned successfully.", document_id)
                except Exception as ai_err:
                    logger.warning("[Doc %d] AI analysis failed: %s", document_id, ai_err)

                # Fallback: if AI failed or missed key sections, run regex
                try:
                    from app.services.metadata_extraction import metadata_extraction_service
                    regex_meta = await metadata_extraction_service.extract_metadata(normalized_text, language)
                    
                    # Merge regex fallbacks and align keys
                    # DocumentIntelligence uses "key_dates", "financial_terms", "missing_items"
                    # But the rest of this service expects "dates", "amounts", "missing_documents"
                    
                    if not ai_analysis.get("parties"):
                        ai_analysis["parties"] = regex_meta.get("entities", [])
                    
                    if not ai_analysis.get("dates"):
                        # Use key_dates from AI if available, else regex dates
                        ai_analysis["dates"] = ai_analysis.get("key_dates") or regex_meta.get("dates", [])
                    
                    if not ai_analysis.get("amounts"):
                        # Use financial_terms from AI if available, else regex amounts
                        ai_analysis["amounts"] = ai_analysis.get("financial_terms") or regex_meta.get("amounts", [])
                    
                    if not ai_analysis.get("case_numbers"):
                        ai_analysis["case_numbers"] = regex_meta.get("case_numbers", [])
                    
                    if not ai_analysis.get("classification"):
                        ai_analysis["classification"] = ai_analysis.get("document_type") or "Unknown Document"

                    if not ai_analysis.get("missing_documents"):
                        ai_analysis["missing_documents"] = ai_analysis.get("missing_items") or []

                    # Update document record with classification from AI
                    document = await document_crud.get(db, document_id)
                    if document:
                        document.classification = ai_analysis.get("classification") or "Unknown Document"
                        await db.commit()

                    # We explicitly empty routing fields to avoid OCR-based tags
                    ai_analysis["routing_ids"] = []
                    ai_analysis["routing_projects"] = []
                    ai_analysis["routing_organizations"] = []
                except Exception as meta_err:
                    logger.warning("[Doc %d] Regex metadata extraction failed: %s", document_id, meta_err)
                    ai_analysis["routing_ids"] = []
                    ai_analysis["routing_projects"] = []
                    ai_analysis["routing_organizations"] = []

                # Build simple confidence votes for AI tags (single-pass analysis)
                try:
                    tag_votes = []
                    for t in ai_analysis.get("tags", []) or []:
                        tag_votes.append({"name": t, "confidence": 0.5})
                    ai_analysis["tag_votes"] = tag_votes
                except Exception:
                    pass

                # ── STEP 4: Store metadata + summary ─────────────────────────────
                await self._store_metadata_and_summary(db, document_id, organization_id, ai_analysis)

                if await _abort_if_timed_out("metadata_saved"):
                    return

                # ── STEP 4.5: Deadline Extraction ───────────────────────────────
                logger.info("[Doc %d] Extracting deadlines...", document_id)
                try:
                    # 1. First, check if LLM already extracted high-quality deadlines
                    llm_dates = ai_analysis.get("key_dates", [])
                    extracted_deadlines = []
                    
                    # Map LLM types to our Enum
                    type_map = {
                        "hearing": DeadlineType.HEARING,
                        "filing": DeadlineType.FILING,
                        "response": DeadlineType.RESPONSE,
                        "appeal": DeadlineType.APPEAL,
                        "statute_of_limitations": DeadlineType.STATUTE_OF_LIMITATIONS
                    }

                    for d in llm_dates:
                        # Map LLM type string to enum
                        llm_type_str = str(d.get("type", "other")).lower()
                        mapped_type = type_map.get(llm_type_str, DeadlineType.OTHER)
                        
                        # Include if it's marked critical OR has a legal type OR just has a good description
                        is_critical = d.get("is_critical_deadline")
                        if isinstance(is_critical, str):
                            is_critical = is_critical.lower() == 'true'
                            
                        if is_critical or mapped_type != DeadlineType.OTHER or d.get("description"):
                            try:
                                d_date_str = d.get("date")
                                # Try a few formats if strptime fails
                                d_date = dateparser.parse(d_date_str)
                                if d_date:
                                    extracted_deadlines.append({
                                        "date": d_date,
                                        "type": mapped_type,
                                        "description": d.get("description", "Legal Deadline"),
                                        "confidence": 0.95
                                    })
                            except:
                                continue

                    # 2. Fallback/Augment with NER
                    ner_results = ner_service.extract_deadlines(normalized_text, language=language)
                    # Deduplicate: if we already have a date on this day, skip NER
                    existing_days = {n["date"].date() for n in extracted_deadlines}
                    for n in ner_results:
                        if n["date"].date() not in existing_days:
                            extracted_deadlines.append(n)

                    # 3. Save to DB
                    for d_info in extracted_deadlines:
                        new_deadline = Deadline(
                            document_id=document_id,
                            case_id=document.case_id,
                            organization_id=organization_id,
                            deadline_date=d_info["date"],
                            deadline_type=d_info["type"],
                            description=d_info["description"],
                            confidence_score=d_info["confidence"]
                        )
                        db.add(new_deadline)
                    await db.commit()
                    logger.info("[Doc %d] Processed %d legal deadlines.", document_id, len(extracted_deadlines))
                except Exception as deadline_err:
                    logger.warning("[Doc %d] Deadline extraction failed: %s", document_id, deadline_err)

                document = await document_crud.get(db, document_id)
                if not document:
                    return
                await _set_status(db, document, DocumentProcessingStatus.PROCESSING,
                                  "metadata_saved", 50.0)

                # ── STEP 5: Smart Collections routing ────────────────────────────
                try:
                    await smart_collections_service.route_document_to_collections(
                        db, document, ai_analysis
                    )
                    logger.info("[Doc %d] Smart Collections routing complete.", document_id)
                except Exception as sc_err:
                    logger.warning("[Doc %d] Smart Collections routing failed (non-fatal): %s",
                                   document_id, sc_err)

                # ── STEP 6: Chunk & embed ────────────────────────────────────────
                document = await document_crud.get(db, document_id)
                if not document:
                    return
                if await _abort_if_timed_out("embedding"):
                    return
                await self._chunk_and_embed(db, document, normalized_text,
                                            progress_start=50.0, progress_end=95.0)

                # ── STEP 7: Finalise ─────────────────────────────────────────────
                document = await document_crud.get(db, document_id)
                if not document:
                    return
                await _set_status(db, document, DocumentProcessingStatus.COMPLETED,
                                  "completed", 100.0)
                logger.info("[Doc %d] ✅ Processing complete.", document_id)

                # Broadcast WebSocket event (non-fatal)
                try:
                    from app.api.ws.notifications import notification_manager
                    await notification_manager.broadcast_to_organization(
                        organization_id,
                        {
                            "type": "DOCUMENT_PROCESSED",
                            "document_id": document_id,
                            "message": f"Document '{document.filename}' is ready.",
                        },
                    )
                except Exception:
                    pass

            except Exception as exc:
                logger.exception("[Doc %d] Unexpected pipeline failure: %s", document_id, exc)
                try:
                    await db.rollback()
                    document_fail = await document_crud.get(db, document_id)
                    if document_fail:
                        await _set_status(db, document_fail, DocumentProcessingStatus.FAILED,
                                         "pipeline_error", document_fail.processing_progress or 0.0)
                        # Persist structured error log for observability and retries
                        log_entry = DocumentProcessingLog(
                            document_id=document_id,
                            stage=document_fail.processing_stage or "pipeline_error",
                            error_message=str(exc),
                            stack_trace="".join(tb.format_exception(type(exc), exc, exc.__traceback__)),
                        )
                        db.add(log_entry)
                        await db.commit()
                except Exception:
                    pass
                # Broadcast failure
                try:
                    from app.api.ws.notifications import notification_manager
                    await notification_manager.broadcast_to_organization(
                        organization_id,
                        {"type": "DOCUMENT_PROCESSED", "document_id": document_id,
                         "message": "Processing failed."},
                    )
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _store_metadata_and_summary(
        self,
        db: AsyncSession,
        document_id: int,
        organization_id: Optional[int],
        ai_analysis: Dict[str, Any],
    ):
        """Idempotent helper to store extracted metadata arrays and summary text."""
        all_dates = ai_analysis.get("dates", [])
        all_amounts = ai_analysis.get("amounts", [])
        all_case_numbers = ai_analysis.get("case_numbers", [])
        all_missing = ai_analysis.get("missing_documents", [])
        summary_text = ai_analysis.get("summary")

        # Overwrite existing Metadata
        await db.execute(delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id))
        metadata = DocumentMetadata(
            document_id=document_id,
            dates=_dedup(all_dates),
            entities=_extract_rich_entities(ai_analysis),
            amounts=_dedup(all_amounts),
            case_numbers=_dedup(all_case_numbers)
        )
        db.add(metadata)

        # Overwrite existing Summary
        await db.execute(delete(Summary).where(Summary.document_id == document_id))
        summary_obj = Summary(
            document_id=document_id,
            organization_id=organization_id,
            content=str(summary_text) if summary_text else "No text summary could be generated.",
            key_dates=_dedup(all_dates),
            parties=_dedup([p.get('name') if isinstance(p, dict) else p for p in ai_analysis.get("parties", []) if isinstance(p, (dict, str))]),
            missing_documents_suggestion="\n".join(_dedup(all_missing)) if all_missing else None
        )
        db.add(summary_obj)
        await db.commit()


    async def _chunk_and_embed(
        self,
        db: AsyncSession,
        document: Document,
        text: str,
        progress_start: float,
        progress_end: float,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
    ):
        """
        Splits text, generates vector embeddings, and stores them in DB.
        Updates processing progress continuously.
        Is completely idempotent.
        """
        if not text.strip():
            logger.info("[Doc %d] No text to chunk.", document.id)
            return

        # Simple overlap chunking
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i : i + chunk_size])
            i += chunk_size - chunk_overlap

        total_chunks = len(chunks)
        document.total_chunks = total_chunks
        document.processing_stage = "generating_embeddings"
        await db.commit()

        progress_range = progress_end - progress_start
        progress_per_chunk = progress_range / total_chunks if total_chunks > 0 else 0

        # Idempotent cleanup of old chunks
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        await db.commit()

        # Split by page marker if present to get approximate page numbers
        page_marker = "--- Page Break ---"
        if page_marker in text:
            pages = text.split(f"\n\n{page_marker}\n\n")
        else:
            pages = [text]

        chunk_idx = 0
        for p_idx, p_text in enumerate(pages, start=1):
            # Simple overlap chunking per page
            p_chunks = []
            i = 0
            while i < len(p_text):
                p_chunks.append(p_text[i : i + chunk_size])
                i += chunk_size - chunk_overlap
            
            for chunk_text in p_chunks:
                vector = None
                try:
                    vector = await llm_service.generate_embedding(chunk_text)
                except Exception as e:
                    logger.warning("[Doc %d/Chunk %d] Embedding failed: %s", document.id, chunk_idx + 1, e)

                db_chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_idx,
                    text_content=chunk_text,
                    embedding=vector,
                    page_number=p_idx
                )
                db.add(db_chunk)
                
                # Commit every 5 chunks to balance I/O vs memory
                if chunk_idx % 5 == 0:
                    document.processed_chunks = chunk_idx + 1
                    document.processing_progress = round(progress_start + (progress_per_chunk * (chunk_idx + 1)), 1)
                    await db.commit()
                
                chunk_idx += 1

        document.processed_chunks = chunk_idx
        document.processing_progress = progress_end
        await db.commit()
        logger.info("[Doc %d] Chunks/embeddings stored: %d", document.id, chunk_idx)


document_processing_service = DocumentProcessingService()
