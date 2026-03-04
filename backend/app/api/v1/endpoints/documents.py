from typing import List, Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc

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
from app.db.models.document import Document as DBDocument
from app.db.models.tag import Tag as DBTag
from app.services.llm import llm_service # Import LLM Service for summary generation
from app.services.metadata_extraction import metadata_extraction_service
from app.services.audit import log_audit
from app.services.smart_router import smart_router
from app.services.document_processing_task import document_processing_service
from app.services.smart_collections import smart_collections_service

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
    Upload a new document instantly and trigger async OCR and AI analysis in the background.
    """
    from app.services.storage import storage_service
    from app.services.ocr import ocr_service
    from app.services.document_intelligence import document_intelligence_service
    from app.db.models.case import Case as DBCase
    
    # Verify case exists if provided
    if case_id and case_id != 0:
        case = await db.get(DBCase, case_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case with id {case_id} not found")
    
    # Upload file to storage
    upload_path = f"cases/{case_id}/documents" if case_id and case_id != 0 else "inbox/unprocessed"
    s3_url = await storage_service.upload_file(file, upload_path)
    
    # Get actual file path for background OCR processing
    file_path = await storage_service.get_file_path(f"{upload_path}/{file.filename}")
    
    # 1. Create a placeholder Document in the Database instantly
    document_in = DocumentCreate(
        filename=file.filename or "unknown",
        s3_url=s3_url,
        case_id=case_id if case_id and case_id != 0 else None,
        content="Processing text...",
        classification="Pending Analysis",
        language=None,
        page_count=0,
    )
    document = await document_crud.create(db, document_in, current_user.id, current_user.organization_id)
    
    # 2. Queue Background Task for Heavy AI OCR & Summarization & Vector Embeddings
    background_tasks.add_task(
        document_processing_service.process_document_background,
        db=db,
        document_id=document.id,
        file_path=str(file_path),
        user_id=current_user.id,
        organization_id=current_user.organization_id
    )

    # 3. Audit Log
    try:
        await log_audit(db, current_user, "document_upload", {"document_id": document.id, "filename": document.filename})
    except Exception as e:
        print(f"Failed to create audit log: {e}")
    
    # 4. Return instantly to unblock UI
    # Re-fetch the document with tags eager-loaded to avoid MissingGreenlet errors during Pydantic serialization
    result = await db.execute(
        select(DBDocument).options(selectinload(DBDocument.tags)).filter(DBDocument.id == document.id)
    )
    document_with_tags = result.scalars().first()
    return document_with_tags

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
    
    query = select(DBDocument).options(selectinload(DBDocument.tags)).offset(skip).limit(limit)
    
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
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    document = await document_crud.update(db, document_id, document_in)
    # Optional: Add authorization check
    
    # Audit Log
    await log_audit(db, current_user, "document_update", {"document_id": document.id, "changes": document_in.model_dump(exclude_unset=True)})
    
    return document

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    document = await document_crud.get(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(document, current_user)

    await document_crud.delete(db, document_id)
        
    # Audit Log
    await log_audit(db, current_user, "document_delete", {"document_id": document_id})
    
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
    await log_audit(db, current_user, "document_classify", {"document_id": document.id, "classification": document.classification})
    
    return document

@router.post("/{document_id}/tags", response_model=DocumentSchema)
async def add_tag_to_document(
    document_id: int,
    tag_name: str, # Allow creating new tag or using existing by name
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
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
    """
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
    Returns all structured data: metadata, summary, tags, classification.
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
    
    return {
        "document_id": document.id,
        "filename": document.filename,
        "classification": document.classification,
        "language": document.language,
        "page_count": document.page_count,
        "case_id": document.case_id,
        "created_at": document.created_at,
        "metadata": {
            "dates": metadata.dates if metadata else [],
            "entities": metadata.entities if metadata else [],
            "amounts": metadata.amounts if metadata else [],
            "case_numbers": metadata.case_numbers if metadata else [],
        } if metadata else None,
        "summary": {
            "content": summary.content if summary else None,
            "key_dates": summary.key_dates if summary else [],
            "parties": summary.parties if summary else [],
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
        
    # ------------- SMART COLLECTIONS AUTO-ROUTING -------------
    # Dynamically map the AI-extracted routing keys into Tag Collections
    tags_to_append = []
    org_id = document.organization_id

    for rid in extracted.get("routing_ids", []):
        t = await crud_tag.find_or_create(db, name=str(rid), category="client_id", organization_id=org_id)
        tags_to_append.append(t)

    for proj in extracted.get("routing_projects", []):
        t = await crud_tag.find_or_create(db, name=str(proj), category="project", organization_id=org_id)
        tags_to_append.append(t)

    for org_name in extracted.get("routing_organizations", []):
        t = await crud_tag.find_or_create(db, name=str(org_name), category="organization", organization_id=org_id)
        tags_to_append.append(t)

    if tags_to_append:
        # Load the document's existing tags to append the new ones safely
        await db.refresh(document, ['tags'])
        for t in tags_to_append:
            if t not in document.tags:
                document.tags.append(t)
        await db.commit()
    # ----------------------------------------------------------

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
        document.content, document.filename
    )

    # 2. Merge regex metadata
    try:
        regex_meta = await metadata_extraction_service.extract_metadata(
            document.content, document.language or "en"
        )
        ai_analysis["routing_ids"] = regex_meta.get("routing_ids", [])
        ai_analysis["routing_projects"] = regex_meta.get("routing_projects", [])
        ai_analysis["routing_organizations"] = regex_meta.get("routing_organizations", [])
    except Exception:
        ai_analysis.setdefault("routing_ids", [])
        ai_analysis.setdefault("routing_projects", [])
        ai_analysis.setdefault("routing_organizations", [])

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
                doc.content, doc.filename
            )
            try:
                regex_meta = await metadata_extraction_service.extract_metadata(
                    doc.content, doc.language or "en"
                )
                ai_analysis["routing_ids"] = regex_meta.get("routing_ids", [])
                ai_analysis["routing_projects"] = regex_meta.get("routing_projects", [])
                ai_analysis["routing_organizations"] = regex_meta.get("routing_organizations", [])
            except Exception:
                ai_analysis.setdefault("routing_ids", [])
                ai_analysis.setdefault("routing_projects", [])
                ai_analysis.setdefault("routing_organizations", [])

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
