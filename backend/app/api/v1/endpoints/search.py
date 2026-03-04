from typing import List, Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_db, get_current_active_user, RoleChecker
from app.schemas.document import Document as DocumentSchema
from app.crud.document import document_crud
from app.db.models.user import User as DBUser, UserRole
from app.db.models.document import Document as DBDocument # Added
from app.db.models.tag import Tag as DBTag # Added
from app.services.embeddings import embedding_service # To generate embeddings for semantic search queries

router = APIRouter()

@router.get("/", response_model=List[DocumentSchema])
async def smart_search(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    query_string: Optional[str] = Query(None, description="Keywords for full-text search"),
    semantic_query: Optional[str] = Query(None, description="Phrase for semantic search (will be embedded)"),
    case_id: Optional[int] = Query(None, description="Filter by case ID"),
    language: Optional[str] = Query(None, description="Filter by document language (e.g., 'en', 'he')"),
    classification: Optional[str] = Query(None, description="Filter by document classification (e.g., 'contract')"),
    tags: Optional[List[str]] = Query(None, description="Filter by document tags"),
    limit: int = Query(10, ge=1, le=100),
):
    """
    Perform a smart search across documents, combining full-text and semantic capabilities.
    Results are returned ordered by relevance, with semantic matches prioritized if a semantic query is provided.
    """
    documents = []

    if semantic_query:
        # Generate embeddings for the semantic query
        query_embedding = await embedding_service.generate_embeddings(semantic_query)
        semantic_results = await document_crud.semantic_search(
            db,
            query_embedding=query_embedding,
            case_id=case_id,
            limit=limit,
        )
        documents.extend(semantic_results)
        # For simplicity in MVP, if semantic query is present, it dominates.
        # A more complex system would merge and re-rank results.
        return documents 

    elif query_string:
        # Perform full-text search
        full_text_results = await document_crud.full_text_search(
            db,
            query_string=query_string,
            case_id=case_id,
            language=language,
            classification=classification,
            tag_names=tags,
            limit=limit,
        )
        documents.extend(full_text_results)

    # If no specific search query (semantic or full-text), return filtered results or all documents
    if not documents and (case_id or language or classification or tags):
        # Fallback to filtering documents based on criteria if no search string
        filter_query = select(DBDocument).options(selectinload(DBDocument.tags))
        if case_id:
            filter_query = filter_query.filter(DBDocument.case_id == case_id)
        if language:
            filter_query = filter_query.filter(DBDocument.language == language)
        if classification:
            filter_query = filter_query.filter(DBDocument.classification == classification)
        if tags:
            for tag_name in tags:
                filter_query = filter_query.filter(DBDocument.tags.any(DBTag.name == tag_name))
        
        filter_query = filter_query.offset(0).limit(limit)
        result = await db.execute(filter_query)
        documents.extend(result.scalars().all())

    # If nothing found or no query, but filters are present, it implies general filtering.
    # Otherwise, an empty list is returned.

    return documents
