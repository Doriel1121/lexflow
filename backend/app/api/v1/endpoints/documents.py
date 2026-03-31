from typing import List, Annotated, Optional
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc

from app.core.config import settings
from app.core.dependencies import get_db, get_current_active_user, apply_user_org_filter, RoleChecker, verify_resource_access
from app.db.models.user import User as DBUser, UserRole
from app.schemas.document import DocumentCreate, DocumentUpdate, Document as DocumentSchema
from app.schemas.tag import Tag as TagSchema, TagCreate
from app.schemas.summary import SummaryCreate, Summary as SummarySchema # Import Summary Schemas
from app.schemas.document_metadata import DocumentMetadata as DocumentMetadataSchema, DocumentMetadataCreate
from app.crud.document import document_crud
from app.crud.tag import crud_tag
from app.crud.summary import crud_summary # Import CRUD for Summary
from app.crud.document_metadata import crud_document_metadata
from app.db.models.user import User as DBUser
from app.db.models.document import Document as DBDocument, DocumentProcessingStatus
from app.db.models.tag import Tag as DBTag
from app.services.llm import llm_service # Import LLM Service for summary generation
from app.services.metadata_extraction import metadata_extraction_service
from app.services.audit import log_audit
from app.services.smart_router import smart_router
from app.services.document_processing_task import document_processing_service
from app.services.smart_collections import smart_collections_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/recent")
async def get_recent_documents(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),  # any active role
    limit: int = 5
):
    """
    Get recent documents for dashboard.
    """
    # Store values before query
    user_org_id = current_user.organization_id
    user_id = current_user.id
    user_role = current_user.role.value if current_user.role else None
    
    query = select(DBDocument).order_by(desc(DBDocument.created_at)).limit(limit)
    query = apply_user_org_filter(query, DBDocument, user_id, user_org_id, user_role)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return [{
        "id": d.id,
        "filename": d.filename,
        "case_id": d.case_id,
        "classification": d.classification or "Unknown",
        "created_at": d.created_at.isoformat() if d.created_at else None
    } for d in documents]

@router.post("/", response_model=DocumentSchema, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    case_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Upload a new document instantly and trigger async OCR + AI analysis.

    Processing flow:
      1. Save file to disk.
      2. Insert a placeholder Document row (status=PENDING) — returned immediately.
      3. Try to queue a Celery task (optional fast-path).
      4. If Celery is unavailable, fall back to a FastAPI BackgroundTask.
    The UI polls GET /{id}/status to track progress.
    """
    import traceback as tb
    from app.services.storage import storage_service
    from app.db.models.case import Case as DBCase

    try:
        # ── Validate case if provided ──────────────────────────────────────
        target_org_id = current_user.organization_id
        if case_id and case_id != 0:
            case = await db.get(DBCase, case_id)
            if not case:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case {case_id} not found",
                )
            # Ensure document inherits the case's organization_id
            if case.organization_id:
                target_org_id = case.organization_id

        # ── Save file ──────────────────────────────────────────────────────
        upload_path = (
            f"cases/{case_id}/documents" if case_id and case_id != 0
            else "inbox/unprocessed"
        )
        # upload_file returns (url, file_path_or_key)
        # - For local storage: (url, Path object)
        # - For R2: (url, s3_key string)
        s3_url, file_location = await storage_service.upload_file(file, upload_path)

        # For R2, file_location is the S3 key; for local storage, it's a Path
        # Store the S3 URL in the database (works for both)
        # For file_path passed to processing: if local storage, convert Path to str
        if isinstance(file_location, Path):
            file_path_for_processing = str(file_location)
        else:
            # It's an S3 key from R2
            file_path_for_processing = file_location

        # Decide which processing flow to use
        def _select_processing_flow(file_path_value: str) -> str:
            mode = (settings.DOCUMENT_PROCESSING_MODE or "auto").strip().lower()
            if mode in ("celery", "background"):
                return mode

            # Auto mode: route by file size
            # For R2, we can't easily get file size without downloading, so default to celery
            if settings.R2_ENABLED:
                return "celery"
            
            try:
                size_bytes = Path(file_path_value).stat().st_size
            except Exception:
                size_bytes = None

            if size_bytes is None:
                return "celery"

            min_mb = settings.DOCUMENT_PROCESSING_CELERY_MIN_MB or 0
            return "celery" if size_bytes >= (min_mb * 1024 * 1024) else "background"

        processing_flow = _select_processing_flow(file_path_for_processing)

        # ── Create DB placeholder ──────────────────────────────────────────
        document_in = DocumentCreate(
            filename=file.filename or "unknown",
            s3_url=s3_url,
            case_id=case_id if case_id and case_id != 0 else None,
            content=None,              # will be filled by background processing
            classification="Pending Analysis",
            language=None,
            page_count=0,
        )
        document = await document_crud.create(
            db, document_in, current_user.id, target_org_id
        )

        # ── Queue processing ───────────────────────────────────────────────
        celery_queued = False
        if processing_flow == "celery":
            try:
                from app.workers.document_tasks import process_document_pipeline
                from app.core.celery import safe_task_delay
                safe_task_delay(
                    process_document_pipeline,
                    document_id=document.id,
                    file_path=file_path_for_processing,
                    user_id=current_user.id,
                    organization_id=target_org_id,
                )
                celery_queued = True
                logger.info("[Doc %d] Queued via Celery.", document.id)
            except Exception as celery_err:
                logger.warning(
                    "[Doc %d] Celery unavailable (%s) — falling back to BackgroundTask.",
                    document.id, celery_err,
                )

        if not celery_queued:
            # Always-available fallback: FastAPI BackgroundTask runs in-process
            # Db session is created within the background task itself
            background_tasks.add_task(
                document_processing_service.process_document_background,
                document_id=document.id,
                file_path=file_path_for_processing,
                user_id=current_user.id,
                organization_id=target_org_id,
            )
            logger.info("[Doc %d] Queued via BackgroundTask.", document.id)

        # ── Audit log (non-fatal) ──────────────────────────────────────────
        try:
            await log_audit(
                db=db,
                event_type="document_upload",
                organization_id=target_org_id,
                user_id=current_user.id,
                resource_type="document",
                resource_id=str(document.id),
                metadata_json={"filename": document.filename},
            )
        except Exception as audit_err:
            logger.warning("Audit log failed (non-fatal): %s", audit_err)

        # ── Return immediately ─────────────────────────────────────────────
        result = await db.execute(
            select(DBDocument)
            .options(
                selectinload(DBDocument.tags),
                selectinload(DBDocument.summary),
                selectinload(DBDocument.document_metadata)
            )
            .filter(DBDocument.id == document.id)
        )
        return result.scalars().first()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("UPLOAD ENDPOINT CRASHED:\n%s", tb.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Get real-time granular processing status of a document.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        
    verify_resource_access(document, current_user)
    
    return {
        "id": document.id,
        "status": document.processing_status.value if document.processing_status else "pending",
        "stage": document.processing_stage,
        "progress": document.processing_progress,
        "processed_chunks": document.processed_chunks,
        "total_chunks": document.total_chunks
    }

@router.get("/", response_model=List[DocumentSchema])
async def read_documents(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    skip: int = 0,
    limit: int = 100,
    tag: Optional[int] = None
):
    """
    Retrieve documents filtered by user/organization and optionally by tag.
    """
    # Store org_id before query to avoid lazy loading
    user_org_id = current_user.organization_id
    user_id = current_user.id
    user_role = current_user.role.value if current_user.role else None
    
    query = select(DBDocument).options(
        selectinload(DBDocument.tags),
        selectinload(DBDocument.summary),
        selectinload(DBDocument.document_metadata)
    ).offset(skip).limit(limit)
    
    if tag:
        query = query.join(DBDocument.tags).filter(DBTag.id == tag)
        
    query = apply_user_org_filter(query, DBDocument, user_id, user_org_id, user_role)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    return documents

@router.get("/semantic-search", response_model=List[DocumentSchema])
async def search_documents_semantic(
    query: str,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    limit: int = 10,
    threshold: float = 0.5
):
    """
    Perform a Semantic Search across all indexed document chunks.
    Routes to the PgVector similarity endpoint.
    """
    from sqlalchemy import select
    from app.db.models.document import DocumentChunk
    
    # 1. Generate an embedding vector for the user's search string
    query_vector = await llm_service.generate_embedding(query)
    if not query_vector:
        raise HTTPException(status_code=500, detail="Failed to initialize semantic query vector")
        
    # 2. Search Postgres using L2 Distance (Cosine Similarity via <->)
    user_org_id = current_user.organization_id
    user_id = current_user.id
    user_role = current_user.role.value if current_user.role else None

    # Calculate L2 distance and sort
    stmt = (
        select(DBDocument, DocumentChunk.text_content, DocumentChunk.embedding.l2_distance(query_vector).label('distance'))
        .join(DocumentChunk, DBDocument.id == DocumentChunk.document_id)
        .options(selectinload(DBDocument.tags))
    )
    
    stmt = apply_user_org_filter(stmt, DBDocument, user_id, user_org_id, user_role)
    stmt = stmt.order_by('distance').limit(limit)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    scored_documents = []
    seen_doc_ids = set()
    
    for doc, chunk_text, distance in rows:
        if doc.id not in seen_doc_ids: # Deduplicate if multiple chunks from same doc match
            seen_doc_ids.add(doc.id)
            # Optional: You could attach the relevant snippet back to the document schema, 
            # or just return the base Document model as requested
            scored_documents.append(doc)
            
    return scored_documents

@router.get("/{document_id}", response_model=DocumentSchema)
async def read_document_by_id(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Get a specific document by ID with authorization check.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    verify_resource_access(document, current_user)
    
    return document

@router.put("/{document_id}", response_model=DocumentSchema)
async def update_document(
    document_id: int,
    document_in: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    document = await document_crud.update(db, document_id, document_in)
    # Optional: Add authorization check
    
    # Audit Log
    await log_audit(
        db=db, 
        event_type="document_update", 
        organization_id=current_user.organization_id, 
        user_id=current_user.id,
        resource_type="document",
        resource_id=str(document.id),
        metadata_json={"changes": document_in.model_dump(exclude_unset=True)}
    )
    
    return document

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    from app.services.storage import storage_service

    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    # Save URL before deleting DB row (cascade will wipe it)
    s3_url = document.s3_url

    await document_crud.delete(db, document_id)

    # Delete the physical file from disk (best-effort — never fail the request)
    if s3_url:
        deleted = await storage_service.delete_file_by_url(s3_url)
        if deleted:
            logger.info("[Doc %d] Physical file deleted: %s", document_id, s3_url)
        else:
            logger.warning("[Doc %d] File not found on disk (already deleted?): %s",
                          document_id, s3_url)

    # Audit Log
    await log_audit(
        db=db,
        event_type="document_delete",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="document",
        resource_id=str(document_id),
        metadata_json={},
    )
    return


@router.post("/{document_id}/ocr", response_model=DocumentSchema)
async def trigger_document_ocr(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Re-extract text from document.
    """
    from app.services.ocr import ocr_service
    from pathlib import Path
    
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)
    
    # Get file path
    file_path = Path("/app/backend/uploads") / f"cases/{document.case_id}" / document.filename
    
    # Extract text
    ocr_result = await ocr_service.extract_text_from_file(str(file_path))
    extracted_content = ocr_result["text"]
    language = ocr_result["language"]
    page_count = ocr_result.get("page_count", 0)
    
    document.content = extracted_content
    document.language = language
    document.page_count = page_count
    await db.commit()
    await db.refresh(document)
    return document

@router.post("/{document_id}/classify", response_model=DocumentSchema)
async def classify_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Classify a document automatically.
    (Placeholder: actual classification service integration will be implemented later)
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)
    
    # Simulate classification
    document.classification = "contract" # Simulated classification
    await db.commit()
    await db.refresh(document)
    
    # Audit Log
    await log_audit(
        db=db, 
        event_type="document_classify", 
        organization_id=current_user.organization_id, 
        user_id=current_user.id,
        resource_type="document",
        resource_id=str(document.id),
        metadata_json={"classification": document.classification}
    )
    
    return document

@router.post("/{document_id}/tags", response_model=DocumentSchema)
async def add_tag_to_document(
    document_id: int,
    tag_name: str, # Allow creating new tag or using existing by name
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    tag = await crud_tag.get_by_name(db, tag_name)
    if not tag:
        tag_in = TagCreate(name=tag_name)
        tag = await crud_tag.create(db, tag_in)
    
    document = await document_crud.add_tag_to_document(db, document_id, tag.id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document or Tag not found")
    return document

@router.delete("/{document_id}/tags/{tag_id}", response_model=DocumentSchema)
async def remove_tag_from_document(
    document_id: int,
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    document = await document_crud.remove_tag_from_document(db, document_id, tag_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document or Tag not found")
    return document

# Tags CRUD operations (optional, can be separate endpoint or managed through documents)
@router.post("/tags/", response_model=TagSchema, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_in: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Create a new tag.
    """
    existing_tag = await crud_tag.get_by_name(db, tag_in.name)
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists",
        )
    tag = await crud_tag.create(db, tag_in)
    return tag

@router.get("/tags/", response_model=List[TagSchema])
async def read_tags(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Retrieve tags.
    """
    tags = await crud_tag.get_multi(db, skip=skip, limit=limit)
    return tags

@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Delete a tag.
    """
    tag = await crud_tag.delete(db, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return

@router.post("/{document_id}/summarize", response_model=SummarySchema, status_code=status.HTTP_201_CREATED)
async def trigger_document_summary(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Trigger AI-based summarization for a document.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)
    
    if not document.content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document has no content to summarize")
    
    # Check if a summary already exists
    existing_summary = await crud_summary.get_by_document_id(db, document_id)
    if existing_summary:
        return SummarySchema.model_validate(existing_summary) # Return existing summary

    # Simulate LLM processing
    summary_content = await llm_service.summarize_text(document.content)
    key_dates = await llm_service.extract_key_dates(document.content)
    parties = await llm_service.extract_parties(document.content)
    missing_docs_suggestion = await llm_service.suggest_missing_documents(document.content)

    summary_in = SummaryCreate(
        document_id=document_id,
        content=summary_content,
        key_dates=key_dates,
        parties=parties,
        missing_documents_suggestion=missing_docs_suggestion,
    )
    summary = await crud_summary.create(db, summary_in)
    return summary

@router.get("/{document_id}/summary", response_model=SummarySchema)
async def get_document_summary(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Get the AI-generated summary for a specific document.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    summary = await crud_summary.get_by_document_id(db, document_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found for this document")
    return summary



@router.get("/{document_id}/text")

async def get_document_text(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Retrieve full OCR text, language, and page count for a document.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)
    
    if not document.content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No OCR text available for this document")
    
    return {
        "id": document.id,
        "filename": document.filename,
        "content": document.content,
        "language": document.language or "unknown",
        "page_count": document.page_count or 0,
    }

@router.get("/{document_id}/metadata", response_model=DocumentMetadataSchema)
async def get_document_metadata(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Retrieve extracted metadata (dates, entities, amounts, case numbers) for a document.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)
    
    metadata = await crud_document_metadata.get_by_document_id(db, document_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata not found for this document")
    
    return metadata

@router.get("/{document_id}/intelligence")
async def get_document_intelligence(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Get comprehensive AI-extracted intelligence for a document.
    Returns structured data: metadata, summary, tags, classification.

    Entities are always returned as rich dicts:
      {name, role, id_number, contact, firm, bar_number}
    so the DocumentViewer Entities tab can render all fields without
    needing to normalise on the client side.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    metadata = await crud_document_metadata.get_by_document_id(db, document_id)
    summary = await crud_summary.get_by_document_id(db, document_id)

    result = await db.execute(
        select(DBDocument).options(selectinload(DBDocument.tags)).filter(DBDocument.id == document_id)
    )
    doc_with_tags = result.scalars().first()

    def _normalise_entities(raw: list) -> list:
        """
        Ensure every entity is a rich dict regardless of how it was
        originally stored (legacy plain strings, partial dicts, full dicts).
        """
        normalised = []
        for item in (raw or []):
            if isinstance(item, dict):
                normalised.append({
                    "name":       item.get("name", ""),
                    "role":       item.get("role", ""),
                    "id_number":  item.get("id_number"),
                    "contact":    item.get("contact"),
                    "firm":       item.get("firm"),
                    "bar_number": item.get("bar_number"),
                })
            elif isinstance(item, str) and item.strip():
                normalised.append({
                    "name": item, "role": "", "id_number": None,
                    "contact": None, "firm": None, "bar_number": None,
                })
        return normalised

    def _normalise_dates(raw: list) -> list:
        """Ensure dates are always dicts with {date, description, type}."""
        out = []
        for item in (raw or []):
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str) and item.strip():
                out.append({"date": item, "description": None, "type": None})
        return out

    def _normalise_amounts(raw: list) -> list:
        """Ensure amounts are always dicts with {amount, currency, description, payer, payee}."""
        out = []
        for item in (raw or []):
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str) and item.strip():
                out.append({"amount": item, "currency": None, "description": None,
                            "payer": None, "payee": None})
        return out

    return {
        "document_id": document.id,
        "filename":    document.filename,
        "classification": document.classification,
        "language":    document.language,
        "page_count":  document.page_count,
        "case_id":     document.case_id,
        "created_at":  document.created_at,
        "processing_status": (
            document.processing_status.value if document.processing_status else "pending"
        ),
        "metadata": {
            "dates":        _normalise_dates(metadata.dates if metadata else []),
            "entities":     _normalise_entities(metadata.entities if metadata else []),
            "amounts":      _normalise_amounts(metadata.amounts if metadata else []),
            "case_numbers": metadata.case_numbers if metadata else [],
        } if metadata else None,
        "summary": {
            "content":           summary.content if summary else None,
            "key_dates":         _normalise_dates(summary.key_dates if summary else []),
            "parties":           summary.parties if summary else [],
            "missing_documents": summary.missing_documents_suggestion if summary else None,
        } if summary else None,
        "tags": [tag.name for tag in doc_with_tags.tags] if doc_with_tags else [],
        "content_preview": document.content[:500] if document.content else None,
    }

@router.post("/{document_id}/extract-metadata", response_model=DocumentMetadataSchema)
async def extract_document_metadata(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Extract and store metadata from document text.
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)
    
    if not document.content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document has no content to extract metadata from")
    
    # Extract metadata
    extracted = await metadata_extraction_service.extract_metadata(
        document.content,
        document.language or "en"
    )
    
    # Check if metadata already exists
    existing_metadata = await crud_document_metadata.get_by_document_id(db, document_id)
    
    metadata_in = DocumentMetadataCreate(
        document_id=document_id,
        dates=extracted["dates"],
        entities=extracted["entities"],
        amounts=extracted["amounts"],
        case_numbers=extracted["case_numbers"],
    )
    
    if existing_metadata:
        metadata = await crud_document_metadata.update(db, document_id, metadata_in)
    else:
        metadata = await crud_document_metadata.create(db, metadata_in)

    return metadata


@router.post("/{document_id}/assign-collections", status_code=status.HTTP_200_OK)
async def assign_document_to_collections(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Manually trigger Smart Collections routing for a document that already has content.
    Use this to backfill existing documents that were uploaded before this feature was enabled.
    Returns a summary of collections assigned.
    """
    from app.services.document_intelligence import document_intelligence_service

    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    if not document.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no content yet — wait for processing to complete.",
        )

    # 1. Run AI analysis
    ai_analysis = await document_intelligence_service.analyze_legal_document(
        document.content, document.filename, language=document.language
    )

    # 2. Merge regex metadata — DISABLED to use only AI tags
    ai_analysis["routing_ids"] = []
    ai_analysis["routing_projects"] = []
    ai_analysis["routing_organizations"] = []

    # 3. Run SmartCollections routing
    tags_before = {t.id for t in document.tags}
    await smart_collections_service.route_document_to_collections(db, document, ai_analysis)

    # Reload to see what was added
    updated = await document_crud.get(db, document_id)
    tags_after = updated.tags if updated else []
    new_tags = [t for t in tags_after if t.id not in tags_before]

    return {
        "document_id": document_id,
        "collections_assigned": len(new_tags),
        "collections": [{"id": t.id, "name": t.name, "category": t.category} for t in tags_after],
    }


@router.post("/assign-collections-bulk", status_code=status.HTTP_200_OK)
async def bulk_assign_collections(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
    background_tasks: BackgroundTasks = None,
):
    """
    Backfill Smart Collections for ALL documents in this organisation that have
    content but no collection tags yet. This is run once to catch up documents
    that were uploaded before the Smart Collections feature was enabled.
    Returns immediately and processes in the background.
    """
    from app.services.document_intelligence import document_intelligence_service

    org_id = current_user.organization_id

    # Fetch all completed documents with content for this org
    query = (
        select(DBDocument)
        .options(selectinload(DBDocument.tags))
        .filter(
            DBDocument.organization_id == org_id,
            DBDocument.content.isnot(None),
        )
    )
    result = await db.execute(query)
    all_docs = result.scalars().all()

    # Filter to docs with no smart-collection tags
    COLLECTION_CATEGORIES = {"client_id", "project", "organization", "case_type", "document_type"}
    docs_needing_sync = [
        d for d in all_docs
        if not any(getattr(t, "category", None) in COLLECTION_CATEGORIES for t in d.tags)
    ]

    processed = 0
    for doc in docs_needing_sync:
        try:
            ai_analysis = await document_intelligence_service.analyze_legal_document(
                doc.content, doc.filename, language=doc.language
            )
            # Regex metadata DISABLED for collections
            ai_analysis["routing_ids"] = []
            ai_analysis["routing_projects"] = []
            ai_analysis["routing_organizations"] = []

            await smart_collections_service.route_document_to_collections(db, doc, ai_analysis)
            processed += 1
        except Exception as e:
            # Don't let one failure stop the batch
            pass

    return {
        "total_documents": len(all_docs),
        "synced": processed,
        "already_categorized": len(all_docs) - len(docs_needing_sync),
    }


@router.post("/retry-ai-analysis/{document_id}", status_code=status.HTTP_200_OK)
async def retry_ai_analysis(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Retry AI analysis for a document that was completed without AI (due to quota or errors).
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    verify_resource_access(document, current_user)
    
    if not document.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no content to analyze"
        )
    
    # Reset processing status
    document.processing_status = DocumentProcessingStatus.PROCESSING
    document.processing_stage = "retrying_ai_analysis"
    document.processing_progress = 10.0
    await db.commit()
    
    # Queue the processing task again
    from app.workers.document_tasks import process_document_pipeline
    from app.core.celery import safe_task_delay
    from app.services.storage import storage_service
    
    try:
        # Get file path
        file_path = await storage_service.get_file_path(
            f"inbox/unprocessed/{document.filename}" if not document.case_id 
            else f"cases/{document.case_id}/documents/{document.filename}"
        )
        
        safe_task_delay(
            process_document_pipeline,
            document_id=document.id,
            file_path=str(file_path),
            user_id=current_user.id,
            organization_id=document.organization_id
        )
        
        return {
            "message": "AI analysis queued for retry",
            "document_id": document_id,
            "status": "processing"
        }
    except Exception as e:
        logger.error(f"Failed to queue retry for document {document_id}: {e}")
        document.processing_status = DocumentProcessingStatus.FAILED
        document.processing_stage = "retry_queue_failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue retry: {str(e)}"
        )
