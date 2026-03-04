import asyncio
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks

from app.db.models.document import Document, DocumentProcessingStatus, DocumentChunk
from app.crud.document import document_crud
from app.services.llm import llm_service
from app.services.ocr import ocr_service
from app.services.document_intelligence import document_intelligence_service
from app.services.metadata_extraction import metadata_extraction_service
from app.api.ws.notifications import notification_manager
from app.schemas.document_metadata import DocumentMetadataCreate
from app.crud.document_metadata import crud_document_metadata
from app.schemas.summary import SummaryCreate
from app.crud.summary import crud_summary
from app.schemas.tag import TagCreate
from app.crud.tag import crud_tag
from app.services.audit import log_audit
from app.services.smart_collections import smart_collections_service

logger = logging.getLogger(__name__)

class DocumentProcessingService:
    async def process_document_background(
        self,
        db: AsyncSession,
        document_id: int,
        file_path: str,
        user_id: int,
        organization_id: int
    ):
        """
        The background worker that executes the heavy AI OCR, Classification, Summarization, and Vector Embeddings.
        """
        try:
            # 1. Start Processing
            document = await document_crud.get(db, document_id)
            if not document:
                print(f"Background Task Error: Document {document_id} not found.")
                return

            document.processing_status = DocumentProcessingStatus.PROCESSING
            await db.commit()

            # 2. Extract Text (OCR)
            ocr_result = await ocr_service.extract_text_from_file(file_path)
            extracted_content = ocr_result["text"]
            document.content = extracted_content
            document.language = ocr_result["language"]
            document.page_count = ocr_result.get("page_count", 0)
            await db.commit()

            # 3. AI Analysis (Insights, Entities, Summaries)
            ai_analysis = await document_intelligence_service.analyze_legal_document(
                extracted_content,
                document.filename
            )

            # 3a. Regex Metadata Extraction — merge routing signals into ai_analysis
            #     so SmartCollectionsService can use routing_ids / routing_projects / routing_organizations
            try:
                language = document.language or "en"
                regex_metadata = await metadata_extraction_service.extract_metadata(
                    extracted_content, language
                )
                ai_analysis["routing_ids"] = regex_metadata.get("routing_ids", [])
                ai_analysis["routing_projects"] = regex_metadata.get("routing_projects", [])
                ai_analysis["routing_organizations"] = regex_metadata.get("routing_organizations", [])
            except Exception as meta_err:
                logger.warning("Metadata extraction failed during background processing: %s", meta_err)
                ai_analysis.setdefault("routing_ids", [])
                ai_analysis.setdefault("routing_projects", [])
                ai_analysis.setdefault("routing_organizations", [])

            # Map Analysis to DB
            document.classification = f"{ai_analysis.get('document_type', 'unclassified')} - {ai_analysis.get('document_subtype', '')}"
            await db.commit()

            # Create Structured Metadata & Summary
            await self._store_metadata_and_summary(db, document_id, ai_analysis)

            # 4a. AUTO-ROUTING — assign document to Smart Collections
            #     Reload document so we have the latest state before tagging
            document = await document_crud.get(db, document_id)
            if document:
                logger.info(
                    "SmartCollections routing document %d | type=%s | parties=%d | routing_ids=%s | routing_projects=%s",
                    document_id,
                    ai_analysis.get("document_type", "?"),
                    len(ai_analysis.get("parties", [])),
                    ai_analysis.get("routing_ids", []),
                    ai_analysis.get("routing_projects", []),
                )
                await smart_collections_service.route_document_to_collections(
                    db, document, ai_analysis
                )
            else:
                logger.warning("SmartCollections: document %d not found after reload", document_id)
            # 4b. Generate Vector Embeddings (PgVector Chunking)
            await self._generate_and_store_vectors(db, document_id, extracted_content)

            # 5. Mark as Completed
            document.processing_status = DocumentProcessingStatus.COMPLETED
            await db.commit()

            # 6. Push WebSocket Event to UI
            await notification_manager.broadcast_to_organization(
                organization_id,
                {
                    "type": "DOCUMENT_PROCESSED",
                    "document_id": document_id,
                    "message": f"AI Analysis complete for {document.filename}"
                }
            )

        except Exception as e:
            print(f"CRITICAL: Background Process failed for Document {document_id}: {str(e)}")
            # Must rollback the failed transaction before making new DB queries
            await db.rollback()
            
            document = await document_crud.get(db, document_id)
            if document:
                document.processing_status = DocumentProcessingStatus.FAILED
                await db.commit()
                
                # Push WebSocket Event to UI to clear the skeleton loader
                await notification_manager.broadcast_to_organization(
                    organization_id,
                    {
                        "type": "DOCUMENT_PROCESSED",
                        "document_id": document_id,
                        "message": f"AI extraction failed."
                    }
                )

    async def _store_metadata_and_summary(self, db: AsyncSession, document_id: int, ai_analysis: dict):
        """Helper to map AI dictionary response to PostgreSQL tables."""
        metadata_in = DocumentMetadataCreate(
            document_id=document_id,
            dates=ai_analysis.get("key_dates", []),
            entities=ai_analysis.get("parties", []) + ai_analysis.get("attorneys", []),
            amounts=ai_analysis.get("financial_terms", []),
            case_numbers=[c for c in ai_analysis.get("case_numbers", []) if c],
        )
        await crud_document_metadata.create(db, metadata_in)

        # Auto-create tags from AI analysis
        for tag_name in ai_analysis.get("tags", [])[:5]:
            tag = await crud_tag.get_by_name(db, tag_name)
            if not tag:
                tag_in = TagCreate(name=tag_name)
                tag = await crud_tag.create(db, tag_in)
            await document_crud.add_tag_to_document(db, document_id, tag.id)

        summary_content = f"Type: {ai_analysis.get('document_type', 'Unknown')}\nSUMMARY: {ai_analysis.get('summary', '')}"
        summary_in = SummaryCreate(
            document_id=document_id,
            content=summary_content,
            key_dates=[d.get("date", "") for d in ai_analysis.get("key_dates", []) if d.get("date")],
            parties=[p.get("name", "") for p in ai_analysis.get("parties", []) if p.get("name")],
            missing_documents_suggestion="\n".join(ai_analysis.get("related_documents", [])),
        )
        await crud_summary.create(db, summary_in)

    async def _generate_and_store_vectors(self, db: AsyncSession, document_id: int, full_text: str):
        """
        Chunks the document text and calls llm_service to generate fixed-length vector arrays 
        before storing them into the PgVector database index.
        """
        if not full_text:
            return

        # Basic naive chunking strategy (e.g., 2000 chars per chunk)
        chunk_size = 2000
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

        for index, text_chunk in enumerate(chunks):
            try:
                # Call Gemini LLM or OpenAI to generate the mathematical embedding array
                # Ensure your llm_service has a `generate_embedding` method returning a List[float]
                vector_array = await llm_service.generate_embedding(text_chunk)
                
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=index,
                    text_content=text_chunk,
                    embedding=vector_array
                )
                db.add(db_chunk)
            except Exception as e:
                print(f"Failed to generate embedding for chunk {index}: {e}")

        await db.commit()

document_processing_service = DocumentProcessingService()
