"""
Document Processing Service — Per-Stage Session Architecture
============================================================

Proper transaction handling by using fresh DB sessions for each major 
processing stage. This prevents "aborted transaction" errors and ensures 
status updates complete even if individual stages fail.

Pipeline stages:
  1. OCR (fresh session) → extract text
  2. AI Analysis (fresh session) → legal intelligence  
  3. Metadata (fresh session) → save extracted data
  4. Smart Collections (fresh session) → route document
  5. Chunking & Embeddings (fresh session) → vector DB
  6. Final Status (fresh session) → mark COMPLETED
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


async def _update_status(
    document_id: int,
    status: DocumentProcessingStatus,
    stage: str,
    progress: float,
    *,
    organization_id: int | None = None,
):
    """Update document status using fresh session and publish via Redis pub/sub."""
    try:
        async with AsyncSessionLocal() as db:
            document = await document_crud.get(db, document_id)
            if document:
                document.processing_status = status
                document.processing_stage = stage
                document.processing_progress = round(progress, 1)
                await db.commit()
                logger.debug(f"[Doc {document_id}] Status: {stage} ({progress}%)")

                # Publish status update via Redis for instant WebSocket delivery
                org_id = organization_id or document.organization_id
                if org_id:
                    try:
                        from app.api.ws.notifications import publish_notification
                        from app.db.models.user import User

                        result = await db.execute(
                            select(User.id).where(User.organization_id == org_id)
                        )
                        user_ids = result.scalars().all()
                        ws_payload = {
                            "type": "DOCUMENT_STATUS_UPDATE",
                            "document_id": document_id,
                            "stage": stage,
                            "progress": round(progress, 1),
                        }
                        for uid in user_ids:
                            await publish_notification(uid, ws_payload)
                    except Exception as pub_err:
                        logger.debug(f"[Doc {document_id}] Redis pub failed (non-fatal): {pub_err}")
    except Exception as e:
        logger.warning(f"[Doc {document_id}] Failed to update status: {e}")


async def _set_status_fresh(
    document_id: int,
    status: DocumentProcessingStatus,
    stage: str,
    progress: float,
):
    """Update document status using a fresh session. Safe for use after corrupted sessions."""
    try:
        async with AsyncSessionLocal() as fresh_db:
            document = await document_crud.get(fresh_db, document_id)
            if document:
                document.processing_status = status
                document.processing_stage = stage
                document.processing_progress = round(progress, 1)
                await fresh_db.commit()
                logger.info(f"[Doc {document_id}] Status updated (fresh session): {stage}")
    except Exception as e:
        logger.warning(f"[Doc {document_id}] Failed to update status in fresh session: {e}")


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
        Document processing with per-stage fresh sessions.
        Each major stage gets its own database session to prevent
        transaction corruption from propagating through the pipeline.
        """
        logger.info(f"[Doc {document_id}] Pipeline started. file={file_path}")
        start_time = time.time()

        # ── INIT: Mark as processing ──────────────────────────────────────
        await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ocr_started", 5.0)

        try:
            # ── STAGE 1: OCR ──────────────────────────────────────────────
            logger.info(f"[Doc {document_id}] Stage 1: Running OCR...")
            ocr_result = await self._stage_ocr(document_id, file_path)
            if not ocr_result:
                await _update_status(document_id, DocumentProcessingStatus.FAILED, "ocr_failed", 5.0)
                return

            extracted_text, normalized_text, language, page_count = ocr_result
            logger.info(f"[Doc {document_id}] OCR done: {len(extracted_text)} chars, {page_count} pages")
            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ocr_completed", 20.0)

            if not extracted_text.strip():
                await _update_status(document_id, DocumentProcessingStatus.FAILED, "ocr_empty_text", 20.0)
                return

            # ── STAGE 2: AI Analysis ──────────────────────────────────────
            logger.info(f"[Doc {document_id}] Stage 2: Running AI analysis...")
            ai_analysis = await self._stage_ai_analysis(
                document_id, normalized_text, language, organization_id
            )
            logger.info(f"[Doc {document_id}] AI analysis done")
            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ai_completed", 35.0)

            # ── STAGE 3: Save metadata & classification ───────────────────
            logger.info(f"[Doc {document_id}] Stage 3: Saving metadata...")
            await self._stage_save_metadata(
                document_id, organization_id, normalized_text, language, ai_analysis
            )
            logger.info(f"[Doc {document_id}] Metadata saved")
            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "metadata_saved", 50.0)

            # ── STAGE 4: Smart Collections routing ─────────────────────────
            logger.info(f"[Doc {document_id}] Stage 4: Smart Collections routing...")
            await self._stage_smart_routing(document_id)
            logger.info(f"[Doc {document_id}] Smart routing done")

            # ── STAGE 5: Chunk & Embed ────────────────────────────────────
            logger.info(f"[Doc {document_id}] Stage 5: Chunking and embedding...")
            await self._stage_chunk_and_embed(document_id, normalized_text)
            logger.info(f"[Doc {document_id}] Chunking done")
            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "embedding_completed", 95.0)

            # ── FINAL: Mark complete ──────────────────────────────────────
            logger.info(f"[Doc {document_id}] ✅ Marking complete...")
            await _update_status(
                document_id, DocumentProcessingStatus.COMPLETED, "completed", 100.0,
                organization_id=organization_id,
            )

            # Send completion notification via Redis pub/sub
            try:
                from app.api.ws.notifications import publish_notification
                from app.db.models.user import User
                from app.db.models.notification import Notification

                async with AsyncSessionLocal() as db:
                    doc = await document_crud.get(db, document_id)
                    result = await db.execute(
                        select(User.id).where(User.organization_id == organization_id)
                    )
                    org_user_ids = result.scalars().all()

                    # Persist notifications
                    for uid in org_user_ids:
                        db.add(Notification(
                            user_id=uid,
                            organization_id=organization_id,
                            type="DOCUMENT_PROCESSED",
                            title="Document Processed",
                            message=f"Document '{doc.filename}' is ready." if doc else "Document processed.",
                            source_type="document",
                            source_id=document_id,
                            read=False,
                        ))
                    await db.commit()

                    # Publish via Redis for instant delivery
                    ws_payload = {
                        "type": "DOCUMENT_PROCESSED",
                        "title": "Document Processed",
                        "message": f"Document '{doc.filename}' is ready." if doc else "Document processed.",
                        "document_id": document_id,
                    }
                    for uid in org_user_ids:
                        await publish_notification(uid, ws_payload)
            except Exception as notif_err:
                logger.warning(f"[Doc {document_id}] Completion notification failed: {notif_err}")

            elapsed = time.time() - start_time
            logger.info(f"[Doc {document_id}] ✅ COMPLETED in {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"[Doc {document_id}] PIPELINE FAILED: {e}\n{tb.format_exc()}")
            await _update_status(document_id, DocumentProcessingStatus.FAILED, "pipeline_error", 0.0)

            # Log error for debugging
            try:
                async with AsyncSessionLocal() as db:
                    error_log = DocumentProcessingLog(
                        document_id=document_id,
                        stage="pipeline_error",
                        error_message=str(e),
                        stack_trace=tb.format_exc(),
                    )
                    db.add(error_log)
                    await db.commit()
            except:
                pass

    # ─────────────────────────────────────────────────────────────────────
    # Stage handlers (each gets fresh session)
    # ─────────────────────────────────────────────────────────────────────

    async def _stage_ocr(self, document_id: int, file_path: str) -> Optional[tuple]:
        """OCR stage with fresh session."""
        try:
            ocr_result = await ocr_service.extract_text_from_file(file_path)
            extracted_text = ocr_result.get("text", "") or ""
            normalized_text = text_normalization_service.normalize(
                extracted_text, language=ocr_result.get("language", "en")
            )
            language = ocr_result.get("language", "en")
            page_count = ocr_result.get("page_count", 0)

            # Save OCR results
            async with AsyncSessionLocal() as db:
                document = await document_crud.get(db, document_id)
                if document:
                    document.content = normalized_text
                    document.language = language
                    document.page_count = page_count
                    await db.commit()

            return extracted_text, normalized_text, language, page_count
        except Exception as e:
            logger.error(f"[Doc {document_id}] OCR failed: {e}")
            return None

    async def _stage_ai_analysis(
        self,
        document_id: int,
        normalized_text: str,
        language: str,
        organization_id: Optional[int],
    ) -> Dict[str, Any]:
        """AI analysis stage with fresh session."""
        ai_analysis = {}
        try:
            # Get battery save setting
            async with AsyncSessionLocal() as db:
                from app.db.models.organization import Organization
                org = await db.get(Organization, organization_id)
                battery_save = org.ai_battery_save_mode if org else False

            input_text = normalized_text
            if battery_save and len(normalized_text) > 25000:
                logger.info(f"[Doc {document_id}] Battery save: truncating to ~25k chars")
                input_text = normalized_text[:15000] + "\n\n[... TEXT TRUNCATED ...]\n\n" + normalized_text[-10000:]

            ai_analysis = await document_intelligence_service.analyze_legal_document(
                input_text,
                filename=f"doc_{document_id}",
                language=language,
            )
        except Exception as e:
            logger.warning(f"[Doc {document_id}] AI analysis failed: {e}")

        # Fallback: regex extraction
        try:
            from app.services.metadata_extraction import metadata_extraction_service
            regex_meta = await metadata_extraction_service.extract_metadata(normalized_text, language)

            if not ai_analysis.get("parties"):
                ai_analysis["parties"] = regex_meta.get("entities", [])
            if not ai_analysis.get("dates"):
                ai_analysis["dates"] = regex_meta.get("dates", [])
            if not ai_analysis.get("amounts"):
                ai_analysis["amounts"] = regex_meta.get("amounts", [])
            if not ai_analysis.get("case_numbers"):
                ai_analysis["case_numbers"] = regex_meta.get("case_numbers", [])
            if not ai_analysis.get("classification"):
                ai_analysis["classification"] = "Unknown Document"
            if not ai_analysis.get("missing_documents"):
                ai_analysis["missing_documents"] = []

            ai_analysis["routing_ids"] = []
            ai_analysis["routing_projects"] = []
            ai_analysis["routing_organizations"] = []
        except Exception as e:
            logger.warning(f"[Doc {document_id}] Regex extraction failed: {e}")
            # Ensure analysis has required fields
            for key in ["classification", "parties", "dates", "amounts", "case_numbers", "missing_documents"]:
                if key not in ai_analysis:
                    ai_analysis[key] = [] if key != "classification" else "Unknown Document"

        return ai_analysis

    async def _stage_save_metadata(
        self,
        document_id: int,
        organization_id: Optional[int],
        normalized_text: str,
        language: str,
        ai_analysis: Dict[str, Any],
    ):
        """Save metadata, summary, and extraction deadlines."""
        try:
            async with AsyncSessionLocal() as db:
                document = await document_crud.get(db, document_id)
                if not document:
                    return

                # Update classification
                classification = ai_analysis.get("classification", "Unknown Document")
                document.classification = classification
                await db.commit()

                # Save metadata
                await db.execute(delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id))
                metadata = DocumentMetadata(
                    document_id=document_id,
                    dates=_dedup(ai_analysis.get("dates", [])),
                    entities=_extract_rich_entities(ai_analysis),
                    amounts=_dedup(ai_analysis.get("amounts", [])),
                    case_numbers=_dedup(ai_analysis.get("case_numbers", []))
                )
                db.add(metadata)
                await db.commit()

                # Save summary
                await db.execute(delete(Summary).where(Summary.document_id == document_id))
                summary_obj = Summary(
                    document_id=document_id,
                    organization_id=organization_id,
                    content=ai_analysis.get("summary", "No summary available"),
                    key_dates=_dedup(ai_analysis.get("dates", [])),
                    parties=_dedup([p.get("name") if isinstance(p, dict) else p 
                                    for p in ai_analysis.get("parties", []) 
                                    if isinstance(p, (dict, str))]),
                    missing_documents_suggestion="\n".join(ai_analysis.get("missing_documents", []))
                )
                db.add(summary_obj)
                await db.commit()

                # Save deadlines
                extracted_deadlines = []
                llm_dates = ai_analysis.get("key_dates", [])
                type_map = {
                    "hearing": DeadlineType.HEARING,
                    "filing": DeadlineType.FILING,
                    "response": DeadlineType.RESPONSE,
                    "appeal": DeadlineType.APPEAL,
                    "statute_of_limitations": DeadlineType.STATUTE_OF_LIMITATIONS
                }

                for d in llm_dates:
                    try:
                        llm_type_str = str(d.get("type", "other")).lower()
                        mapped_type = type_map.get(llm_type_str, DeadlineType.OTHER)
                        d_date = dateparser.parse(d.get("date"))
                        if d_date:
                            extracted_deadlines.append({
                                "date": d_date,
                                "type": mapped_type,
                                "description": d.get("description", "Legal Deadline"),
                                "confidence": 0.95
                            })
                    except:
                        continue

                # NER fallback
                try:
                    ner_results = ner_service.extract_deadlines(normalized_text, language=language)
                    existing_days = {d["date"].date() for d in extracted_deadlines}
                    for n in ner_results:
                        if n["date"].date() not in existing_days:
                            extracted_deadlines.append(n)
                except:
                    pass

                # Save all deadlines
                for d_info in extracted_deadlines:
                    deadline = Deadline(
                        document_id=document_id,
                        case_id=document.case_id,
                        organization_id=organization_id,
                        deadline_date=d_info["date"],
                        deadline_type=d_info["type"],
                        description=d_info["description"],
                        confidence_score=d_info["confidence"]
                    )
                    db.add(deadline)
                await db.commit()
                logger.info(f"[Doc {document_id}] Saved {len(extracted_deadlines)} deadlines")

        except Exception as e:
            logger.warning(f"[Doc {document_id}] Metadata save failed: {e}")

    async def _stage_smart_routing(self, document_id: int):
        """Smart Collections routing stage."""
        try:
            async with AsyncSessionLocal() as db:
                document = await document_crud.get(db, document_id)
                if document:
                    # Re-fetch AI analysis from metadata
                    result = await db.execute(
                        select(DocumentMetadata).filter(DocumentMetadata.document_id == document_id)
                    )
                    metadata = result.scalars().first()
                    ai_analysis = {
                        "dates": metadata.dates if metadata else [],
                        "case_numbers": metadata.case_numbers if metadata else [],
                    }
                    await smart_collections_service.route_document_to_collections(
                        db, document, ai_analysis
                    )
                    await db.commit()
        except Exception as e:
            logger.warning(f"[Doc {document_id}] Smart routing failed (non-fatal): {e}")

    async def _stage_chunk_and_embed(self, document_id: int, text: str, chunk_size: int = 2000, chunk_overlap: int = 200):
        """Chunk text and generate embeddings."""
        if not text.strip():
            return

        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i : i + chunk_size])
            i += chunk_size - chunk_overlap

        try:
            async with AsyncSessionLocal() as db:
                document = await document_crud.get(db, document_id)
                if not document:
                    return

                # Clear old chunks
                await db.execute(delete(DocumentChunk).filter(DocumentChunk.document_id == document_id))
                await db.commit()

                # Split by page if available
                page_marker = "--- Page Break ---"
                if page_marker in text:
                    pages = text.split(f"\n\n{page_marker}\n\n")
                else:
                    pages = [text]

                chunk_idx = 0
                total_chunks = len(chunks)

                for p_idx, p_text in enumerate(pages, start=1):
                    p_chunks = []
                    i = 0
                    while i < len(p_text):
                        p_chunks.append(p_text[i : i + chunk_size])
                        i += chunk_size - chunk_overlap

                    for chunk_text in p_chunks:
                        vector = None
                        try:
                            vector = await llm_service.generate_embedding(chunk_text)
                        except Exception:
                            pass

                        db_chunk = DocumentChunk(
                            document_id=document_id,
                            chunk_index=chunk_idx,
                            text_content=chunk_text,
                            embedding=vector,
                            page_number=p_idx
                        )
                        db.add(db_chunk)

                        # Commit every 5 chunks
                        if chunk_idx % 5 == 0:
                            document.processed_chunks = chunk_idx + 1
                            document.total_chunks = total_chunks
                            await db.commit()

                        chunk_idx += 1

                document.processed_chunks = chunk_idx
                document.total_chunks = total_chunks
                await db.commit()
                logger.info(f"[Doc {document_id}] Generated {chunk_idx} chunks with embeddings")

        except Exception as e:
            logger.error(f"[Doc {document_id}] Chunking failed: {e}")


document_processing_service = DocumentProcessingService()
