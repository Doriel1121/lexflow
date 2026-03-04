from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.crud.tag import crud_tag
from app.db.models.user import User as DBUser
from app.schemas.tag import Tag, TagCreate

router = APIRouter()

@router.get("", response_model=List[Tag])
async def read_tags(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve tags / collections scoped to the current user's organisation.
    Optionally filter by category: client_id | project | organization | case_type | document_type
    """
    tags = await crud_tag.get_multi_by_organization(
        db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        category=category,
    )
    return tags

@router.get("/{id}", response_model=Tag)
async def read_tag(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Get tag by ID.
    """
    tag = await crud_tag.get(db, id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    if tag.organization_id and tag.organization_id != current_user.organization_id:
        if not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    # Attach document_count (0 for single-tag fetch)
    if not hasattr(tag, "document_count"):
        tag.document_count = 0
    return tag

