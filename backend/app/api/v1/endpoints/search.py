from typing import List, Annotated, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_db, get_current_active_user, RoleChecker, apply_user_org_filter
from app.db.models.user import User as DBUser, UserRole
from app.db.models.document import Document as DBDocument
from app.db.models.case import Case as DBCase
from app.db.models.client import Client as DBClient
from app.schemas.search import GlobalSearchResult

router = APIRouter()

@router.get("/", response_model=GlobalSearchResult)
async def global_search(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_active_user),
    query: str = Query(..., min_length=2, description="The search term"),
    limit_per_type: int = Query(5, ge=1, le=20, description="Max results per category")
):
    """
    Search across multiple entities (Cases, Documents, Clients) and return categorized results.
    """
    user_org_id = current_user.organization_id
    user_id = current_user.id
    user_role = current_user.role.value if current_user.role else None

    # 1. Search Documents (by filename)
    doc_query = select(DBDocument).options(
        selectinload(DBDocument.tags),
        selectinload(DBDocument.summary),
        selectinload(DBDocument.document_metadata)
    ).filter(DBDocument.filename.ilike(f"%{query}%"))
    doc_query = apply_user_org_filter(doc_query, DBDocument, user_id, user_org_id, user_role)
    doc_query = doc_query.limit(limit_per_type)
    
    # 2. Search Cases (by title)
    case_query = select(DBCase).filter(DBCase.title.ilike(f"%{query}%"))
    case_query = apply_user_org_filter(case_query, DBCase, user_id, user_org_id, user_role)
    case_query = case_query.limit(limit_per_type)
    
    # 3. Search Clients (by name)
    client_query = select(DBClient).filter(DBClient.name.ilike(f"%{query}%"))
    # Clients only have organization_id filter
    if user_role != "admin" and user_role != UserRole.ADMIN.value:
        if user_org_id is not None:
            client_query = client_query.where(DBClient.organization_id == user_org_id)
        else:
            # Independent users shouldn't really have clients in this schema yet, 
            # but we'll return nothing for now to be safe
            return GlobalSearchResult()
            
    client_query = client_query.limit(limit_per_type)

    # Execute all queries
    doc_results = await db.execute(doc_query)
    case_results = await db.execute(case_query)
    client_results = await db.execute(client_query)

    return GlobalSearchResult(
        documents=list(doc_results.scalars().all()),
        cases=list(case_results.scalars().all()),
        clients=list(client_results.scalars().all())
    )
