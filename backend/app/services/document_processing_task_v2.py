""""""

































































































































































































































































































































































































































































































































document_processing_service = DocumentProcessingService()            logger.error(f"[Doc {document_id}] Chunking failed: {e}")        except Exception as e:                logger.info(f"[Doc {document_id}] Generated {chunk_idx} chunks with embeddings")                await db.commit()                document.total_chunks = total_chunks                document.processed_chunks = chunk_idx                        chunk_idx += 1                            await db.commit()                            document.total_chunks = total_chunks                            document.processed_chunks = chunk_idx + 1                        if chunk_idx % 5 == 0:                        # Commit every 5 chunks                        db.add(db_chunk)                        )                            page_number=p_idx                            embedding=vector,                            text_content=chunk_text,                            chunk_index=chunk_idx,                            document_id=document_id,                        db_chunk = DocumentChunk(                            pass                        except Exception:                            vector = await llm_service.generate_embedding(chunk_text)                        try:                        vector = None                    for chunk_text in p_chunks:                        i += chunk_size - chunk_overlap                        p_chunks.append(p_text[i : i + chunk_size])                    while i < len(p_text):                    i = 0                    p_chunks = []                for p_idx, p_text in enumerate(pages, start=1):                total_chunks = len(chunks)                chunk_idx = 0                    pages = [text]                else:                    pages = text.split(f"\n\n{page_marker}\n\n")                if page_marker in text:                page_marker = "--- Page Break ---"                # Split by page if available                await db.commit()                await db.execute(delete(DocumentChunk).filter(DocumentChunk.document_id == document_id))                # Clear old chunks                    return                if not document:                document = await document_crud.get(db, document_id)            async with AsyncSessionLocal() as db:        try:            i += chunk_size - chunk_overlap            chunks.append(text[i : i + chunk_size])        while i < len(text):        i = 0        chunks = []            return        if not text.strip():        """Chunk text and generate embeddings."""    async def _stage_chunk_and_embed(self, document_id: int, text: str, chunk_size: int = 2000, chunk_overlap: int = 200):            logger.warning(f"[Doc {document_id}] Smart routing failed (non-fatal): {e}")        except Exception as e:                    await db.commit()                    )                        db, document, ai_analysis                    await smart_collections_service.route_document_to_collections(                    }                        "case_numbers": metadata.case_numbers if metadata else [],                        "dates": metadata.dates if metadata else [],                    ai_analysis = {                    metadata = result.scalars().first()                    )                        select(DocumentMetadata).filter(DocumentMetadata.document_id == document_id)                    result = await db.execute(                    # Re-fetch AI analysis from metadata                if document:                document = await document_crud.get(db, document_id)            async with AsyncSessionLocal() as db:        try:        """Smart Collections routing stage."""    async def _stage_smart_routing(self, document_id: int):            logger.warning(f"[Doc {document_id}] Metadata save failed: {e}")        except Exception as e:                logger.info(f"[Doc {document_id}] Saved {len(extracted_deadlines)} deadlines")                await db.commit()                    db.add(deadline)                    )                        confidence_score=d_info["confidence"]                        description=d_info["description"],                        deadline_type=d_info["type"],                        deadline_date=d_info["date"],                        organization_id=organization_id,                        case_id=document.case_id,                        document_id=document_id,                    deadline = Deadline(                for d_info in extracted_deadlines:                # Save all deadlines                    pass                except:                            extracted_deadlines.append(n)                        if n["date"].date() not in existing_days:                    for n in ner_results:                    existing_days = {d["date"].date() for d in extracted_deadlines}                    ner_results = ner_service.extract_deadlines(normalized_text, language=language)                try:                # NER fallback                        continue                    except:                            })                                "confidence": 0.95                                "description": d.get("description", "Legal Deadline"),                                "type": mapped_type,                                "date": d_date,                            extracted_deadlines.append({                        if d_date:                        d_date = dateparser.parse(d.get("date"))                        mapped_type = type_map.get(llm_type_str, DeadlineType.OTHER)                        llm_type_str = str(d.get("type", "other")).lower()                    try:                for d in llm_dates:                }                    "statute_of_limitations": DeadlineType.STATUTE_OF_LIMITATIONS                    "appeal": DeadlineType.APPEAL,                    "response": DeadlineType.RESPONSE,                    "filing": DeadlineType.FILING,                    "hearing": DeadlineType.HEARING,                type_map = {                llm_dates = ai_analysis.get("key_dates", [])                extracted_deadlines = []                # Save deadlines                await db.commit()                db.add(summary_obj)                )                    missing_documents_suggestion="\n".join(ai_analysis.get("missing_documents", []))                                    if isinstance(p, (dict, str))]),                                    for p in ai_analysis.get("parties", [])                     parties=_dedup([p.get("name") if isinstance(p, dict) else p                     key_dates=_dedup(ai_analysis.get("dates", [])),                    content=ai_analysis.get("summary", "No summary available"),                    organization_id=organization_id,                    document_id=document_id,                summary_obj = Summary(                await db.execute(delete(Summary).where(Summary.document_id == document_id))                # Save summary                await db.commit()                db.add(metadata)                )                    case_numbers=_dedup(ai_analysis.get("case_numbers", []))                    amounts=_dedup(ai_analysis.get("amounts", [])),                    entities=_extract_rich_entities(ai_analysis),                    dates=_dedup(ai_analysis.get("dates", [])),                    document_id=document_id,                metadata = DocumentMetadata(                await db.execute(delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id))                # Save metadata                await db.commit()                document.classification = classification                classification = ai_analysis.get("classification", "Unknown Document")                # Update classification                    return                if not document:                document = await document_crud.get(db, document_id)            async with AsyncSessionLocal() as db:        try:        """Save metadata, summary, and extraction deadlines."""    ):        ai_analysis: Dict[str, Any],        language: str,        normalized_text: str,        organization_id: Optional[int],        document_id: int,        self,    async def _stage_save_metadata(        return ai_analysis                    ai_analysis[key] = [] if key != "classification" else "Unknown Document"                if key not in ai_analysis:            for key in ["classification", "parties", "dates", "amounts", "case_numbers", "missing_documents"]:            # Ensure analysis has required fields            logger.warning(f"[Doc {document_id}] Regex extraction failed: {e}")        except Exception as e:            ai_analysis["routing_organizations"] = []            ai_analysis["routing_projects"] = []            ai_analysis["routing_ids"] = []                ai_analysis["missing_documents"] = []            if not ai_analysis.get("missing_documents"):                ai_analysis["classification"] = "Unknown Document"            if not ai_analysis.get("classification"):                ai_analysis["case_numbers"] = regex_meta.get("case_numbers", [])            if not ai_analysis.get("case_numbers"):                ai_analysis["amounts"] = regex_meta.get("amounts", [])            if not ai_analysis.get("amounts"):                ai_analysis["dates"] = regex_meta.get("dates", [])            if not ai_analysis.get("dates"):                ai_analysis["parties"] = regex_meta.get("entities", [])            if not ai_analysis.get("parties"):            regex_meta = await metadata_extraction_service.extract_metadata(normalized_text, language)            from app.services.metadata_extraction import metadata_extraction_service        try:        # Fallback: regex extraction            logger.warning(f"[Doc {document_id}] AI analysis failed: {e}")        except Exception as e:            )                language=language,                filename=f"doc_{document_id}",                input_text,            ai_analysis = await document_intelligence_service.analyze_legal_document(                input_text = normalized_text[:15000] + "\n\n[... TEXT TRUNCATED ...]\n\n" + normalized_text[-10000:]                logger.info(f"[Doc {document_id}] Battery save: truncating to ~25k chars")            if battery_save and len(normalized_text) > 25000:            input_text = normalized_text                battery_save = org.ai_battery_save_mode if org else False                org = await db.get(Organization, organization_id)                from app.db.models.organization import Organization            async with AsyncSessionLocal() as db:            # Get battery save setting        try:        ai_analysis = {}        """AI analysis stage with fresh session."""    ) -> Dict[str, Any]:        organization_id: Optional[int],        language: str,        normalized_text: str,        document_id: int,        self,    async def _stage_ai_analysis(            return None            logger.error(f"[Doc {document_id}] OCR failed: {e}")        except Exception as e:            return extracted_text, normalized_text, language, page_count                    await db.commit()                    document.page_count = page_count                    document.language = language                    document.content = normalized_text                if document:                document = await document_crud.get(db, document_id)            async with AsyncSessionLocal() as db:            # Save OCR results            page_count = ocr_result.get("page_count", 0)            language = ocr_result.get("language", "en")            )                extracted_text, language=ocr_result.get("language", "en")            normalized_text = text_normalization_service.normalize(            extracted_text = ocr_result.get("text", "") or ""            ocr_result = await ocr_service.extract_text_from_file(file_path)        try:        """OCR stage with fresh session."""    async def _stage_ocr(self, document_id: int, file_path: str) -> Optional[tuple]:    # ─────────────────────────────────────────────────────────────────────    # Stage handlers (each gets fresh session)    # ─────────────────────────────────────────────────────────────────────                pass            except:                    await db.commit()                    db.add(error_log)                    )                        stack_trace=tb.format_exc(),                        error_message=str(e),                        stage="pipeline_error",                        document_id=document_id,                    error_log = DocumentProcessingLog(                async with AsyncSessionLocal() as db:            try:            # Log error for debugging            await _broadcast_status(document_id, organization_id or 0, f"Processing failed: {str(e)}", status="failed")            await _update_status(document_id, DocumentProcessingStatus.FAILED, "pipeline_error", 0.0)            logger.error(f"[Doc {document_id}] PIPELINE FAILED: {e}\n{tb.format_exc()}")        except Exception as e:            logger.info(f"[Doc {document_id}] ✅ COMPLETED in {elapsed:.1f}s")            elapsed = time.time() - start_time            await _broadcast_status(document_id, organization_id or 0, "Processing complete!", status="completed")            await _update_status(document_id, DocumentProcessingStatus.COMPLETED, "completed", 100.0)            logger.info(f"[Doc {document_id}] ✅ Marking complete...")            # ── FINAL: Mark complete ──────────────────────────────────────            await _broadcast_status(document_id, organization_id or 0, "Generating embeddings...")            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "embedding_completed", 95.0)            logger.info(f"[Doc {document_id}] Chunking done")            await self._stage_chunk_and_embed(document_id, normalized_text)            logger.info(f"[Doc {document_id}] Stage 5: Chunking and embedding...")            # ── STAGE 5: Chunk & Embed ────────────────────────────────────            logger.info(f"[Doc {document_id}] Smart routing done")            await self._stage_smart_routing(document_id)            logger.info(f"[Doc {document_id}] Stage 4: Smart Collections routing...")            # ── STAGE 4: Smart Collections routing ─────────────────────────            await _broadcast_status(document_id, organization_id or 0, "Metadata saved")            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "metadata_saved", 50.0)            logger.info(f"[Doc {document_id}] Metadata saved")            )                document_id, organization_id, normalized_text, language, ai_analysis            await self._stage_save_metadata(            logger.info(f"[Doc {document_id}] Stage 3: Saving metadata...")            # ── STAGE 3: Save metadata & classification ───────────────────            await _broadcast_status(document_id, organization_id or 0, "AI analysis complete")            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ai_completed", 35.0)            logger.info(f"[Doc {document_id}] AI analysis done")            )                document_id, normalized_text, language, organization_id            ai_analysis = await self._stage_ai_analysis(            logger.info(f"[Doc {document_id}] Stage 2: Running AI analysis...")            # ── STAGE 2: AI Analysis ──────────────────────────────────────                return                await _update_status(document_id, DocumentProcessingStatus.FAILED, "ocr_empty_text", 20.0)            if not extracted_text.strip():            await _broadcast_status(document_id, organization_id or 0, "Text extraction complete")            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ocr_completed", 20.0)            logger.info(f"[Doc {document_id}] OCR done: {len(extracted_text)} chars, {page_count} pages")            extracted_text, normalized_text, language, page_count = ocr_result                return                await _update_status(document_id, DocumentProcessingStatus.FAILED, "ocr_failed", 5.0)            if not ocr_result:            ocr_result = await self._stage_ocr(document_id, file_path)            logger.info(f"[Doc {document_id}] Stage 1: Running OCR...")            # ── STAGE 1: OCR ──────────────────────────────────────────────        try:        await _broadcast_status(document_id, organization_id or 0, "Starting document processing...")        await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ocr_started", 5.0)        # ── INIT: Mark as processing ──────────────────────────────────────        start_time = time.time()        logger.info(f"[Doc {document_id}] Pipeline started. file={file_path}")        """        Each stage gets a fresh database session, preventing transaction corruption.        Full async document processing pipeline with per-stage sessions.        """    ):        organization_id: Optional[int],        user_id: int,        file_path: str,        document_id: int,        self,    async def process_document_background(    """Document processing with per-stage fresh sessions."""class DocumentProcessingService:        pass    except Exception:        )            }                "message": message,                "status": status,                "document_id": document_id,                "type": "DOCUMENT_STATUS_UPDATE",            {            organization_id,        await notification_manager.broadcast_to_organization(        from app.api.ws.notifications import notification_manager    try:    """Broadcast status update via WebSocket."""async def _broadcast_status(document_id: int, organization_id: int, message: str, status: str = "processing"):        logger.warning(f"[Doc {document_id}] Failed to update status: {e}")    except Exception as e:                logger.debug(f"[Doc {document_id}] Status: {stage} ({progress}%)")                await db.commit()                document.processing_progress = round(progress, 1)                document.processing_stage = stage                document.processing_status = status            if document:            document = await document_crud.get(db, document_id)        async with AsyncSessionLocal() as db:    try:    """Update document status using a fresh session."""):    progress: float,    stage: str,    status: DocumentProcessingStatus,    document_id: int,async def _update_status(    return _dedup(entities)                             "contact": None, "firm": None, "bar_number": None})            entities.append({"name": attorney, "role": "Attorney", "id_number": None,        elif isinstance(attorney, str) and attorney.strip():            })                "bar_number": attorney.get("bar_number"),                "firm": attorney.get("firm"),                "contact": None,                "id_number": None,                "role": f"Attorney representing {attorney.get('representing', '')}".strip(),                "name": attorney.get("name", ""),            entities.append({        if isinstance(attorney, dict):    for attorney in ai_analysis.get("attorneys", []):                             "contact": None, "firm": None, "bar_number": None})            entities.append({"name": party, "role": "Party", "id_number": None,        elif isinstance(party, str) and party.strip():            })                "bar_number": None,                "firm": None,                "contact": party.get("contact"),                "id_number": party.get("id_number"),                "role": party.get("role", ""),                "name": party.get("name", ""),            entities.append({        if isinstance(party, dict):    for party in ai_analysis.get("parties", []):    entities: List[Dict] = []    """Build a unified entity list from AI analysis."""def _extract_rich_entities(ai_analysis: Dict[str, Any]) -> List[Any]:    return out            out.append(item)            seen.add(key)        if key not in seen:        key = str(item)    for item in lst:    seen, out = set(), []    """Deduplicate a list while preserving order."""def _dedup(lst: list) -> list:logger = logging.getLogger(__name__)import traceback as tbfrom app.db.models.document_processing_log import DocumentProcessingLogfrom app.db.session import AsyncSessionLocalfrom app.services.smart_collections import smart_collections_servicefrom app.db.models.deadline import Deadline, DeadlineTypefrom app.services.ai.ner_service import ner_servicefrom app.services.text_normalization import text_normalization_servicefrom app.services.ocr import ocr_servicefrom app.services.llm import llm_servicefrom app.services.document_intelligence import document_intelligence_servicefrom app.services.audit import log_auditfrom app.schemas.tag import TagCreatefrom app.schemas.summary import SummaryCreatefrom app.schemas.document_metadata import DocumentMetadataCreatefrom app.db.models.summary import Summaryfrom app.db.models.document_metadata import DocumentMetadatafrom app.db.models.document import Document, DocumentChunk, DocumentProcessingStatusfrom app.crud.tag import crud_tagfrom app.crud.summary import crud_summaryfrom app.crud.document_metadata import crud_document_metadatafrom app.crud.document import document_crudfrom app.core.config import settingsfrom sqlalchemy.ext.asyncio import AsyncSessionfrom sqlalchemy import delete, selectimport dateparserfrom pathlib import Pathfrom typing import Any, Dict, List, Optionalimport timeimport logging"""  6. Final Status (fresh session)  5. Smart Collections (fresh session)  4. Chunking & Embeddings (fresh session)  3. Metadata & Summary (fresh session)  2. AI Analysis (fresh session)  1. OCR (fresh session)Pipeline stages:ensures status updates complete even if stages fail.major processing stage. This prevents "aborted transaction" errors andProperly handles transaction state by using a fresh session for each============================================================Document Processing Service — Per-Stage Session ArchitectureDocument Processing Service — Per-Stage Session Architecture
============================================================

Properly handles transaction state by using a fresh session for each
major processing stage. This prevents "aborted transaction" errors and
ensures status updates complete even if stages fail.

Pipeline stages:
  1. OCR (fresh session)
  2. AI Analysis (fresh session)
  3. Metadata & Summary (fresh session)
  4. Chunking & Embeddings (fresh session)
  5. Smart Collections (fresh session)
  6. Final Status (fresh session)
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
    """Build a unified entity list from AI analysis."""
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
):
    """Update document status using a fresh session."""
    try:
        async with AsyncSessionLocal() as db:
            document = await document_crud.get(db, document_id)
            if document:
                document.processing_status = status
                document.processing_stage = stage
                document.processing_progress = round(progress, 1)
                await db.commit()
                logger.debug(f"[Doc {document_id}] Status: {stage} ({progress}%)")
    except Exception as e:
        logger.warning(f"[Doc {document_id}] Failed to update status: {e}")


async def _broadcast_status(document_id: int, organization_id: int, message: str, status: str = "processing"):
    """Broadcast status update via WebSocket."""
    try:
        from app.api.ws.notifications import notification_manager
        await notification_manager.broadcast_to_organization(
            organization_id,
            {
                "type": "DOCUMENT_STATUS_UPDATE",
                "document_id": document_id,
                "status": status,
                "message": message,
            }
        )
    except Exception:
        pass


class DocumentProcessingService:
    """Document processing with per-stage fresh sessions."""

    async def process_document_background(
        self,
        document_id: int,
        file_path: str,
        user_id: int,
        organization_id: Optional[int],
    ):
        """
        Full async document processing pipeline with per-stage sessions.
        Each stage gets a fresh database session, preventing transaction corruption.
        """
        logger.info(f"[Doc {document_id}] Pipeline started. file={file_path}")
        start_time = time.time()

        # ── INIT: Mark as processing ──────────────────────────────────────
        await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "ocr_started", 5.0)
        await _broadcast_status(document_id, organization_id or 0, "Starting document processing...")

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
            await _broadcast_status(document_id, organization_id or 0, "Text extraction complete")

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
            await _broadcast_status(document_id, organization_id or 0, "AI analysis complete")

            # ── STAGE 3: Save metadata & classification ───────────────────
            logger.info(f"[Doc {document_id}] Stage 3: Saving metadata...")
            await self._stage_save_metadata(
                document_id, organization_id, normalized_text, language, ai_analysis
            )
            logger.info(f"[Doc {document_id}] Metadata saved")
            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "metadata_saved", 50.0)
            await _broadcast_status(document_id, organization_id or 0, "Metadata saved")

            # ── STAGE 4: Smart Collections routing ─────────────────────────
            logger.info(f"[Doc {document_id}] Stage 4: Smart Collections routing...")
            await self._stage_smart_routing(document_id)
            logger.info(f"[Doc {document_id}] Smart routing done")

            # ── STAGE 5: Chunk & Embed ────────────────────────────────────
            logger.info(f"[Doc {document_id}] Stage 5: Chunking and embedding...")
            await self._stage_chunk_and_embed(document_id, normalized_text)
            logger.info(f"[Doc {document_id}] Chunking done")
            await _update_status(document_id, DocumentProcessingStatus.PROCESSING, "embedding_completed", 95.0)
            await _broadcast_status(document_id, organization_id or 0, "Generating embeddings...")

            # ── FINAL: Mark complete ──────────────────────────────────────
            logger.info(f"[Doc {document_id}] ✅ Marking complete...")
            await _update_status(document_id, DocumentProcessingStatus.COMPLETED, "completed", 100.0)
            await _broadcast_status(document_id, organization_id or 0, "Processing complete!", status="completed")

            elapsed = time.time() - start_time
            logger.info(f"[Doc {document_id}] ✅ COMPLETED in {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"[Doc {document_id}] PIPELINE FAILED: {e}\n{tb.format_exc()}")
            await _update_status(document_id, DocumentProcessingStatus.FAILED, "pipeline_error", 0.0)
            await _broadcast_status(document_id, organization_id or 0, f"Processing failed: {str(e)}", status="failed")

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
