from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.crud.tag import crud_tag, GLOBAL_CATEGORIES
from app.db.models.user import User as DBUser
from app.schemas.tag import Tag, TagUpdate

router = APIRouter()


def _assert_tag_exists(tag: Any) -> None:
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")


def _assert_org_owns_tag(tag: Any, current_user: DBUser) -> None:
    """
    Raise 403 if the tag is org-scoped and belongs to a different org.
    Global const tags (organization_id IS NULL) are readable by all orgs
    but not editable/deletable by any org.
    """
    if tag.organization_id is not None and tag.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this collection",
        )


def _assert_tag_is_editable(tag: Any) -> None:
    """Global const tags (case_type, document_type) are system-managed — not user-editable."""
    if tag.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System collections cannot be edited or deleted",
        )


@router.get("", response_model=List[Tag])
async def read_tags(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 200,
    category: Optional[str] = None,
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    List all collections visible to the current organisation.
    Includes org-scoped tags and global const tags linked to org documents.
    """
    return await crud_tag.get_multi_by_organization(
        db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        category=category,
    )


@router.get("/{id}", response_model=Tag)
async def read_tag(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """Get a single collection by ID."""
    tag = await crud_tag.get(db, id)
    _assert_tag_exists(tag)
    _assert_org_owns_tag(tag, current_user)

    if not hasattr(tag, "document_count"):
        tag.document_count = await crud_tag.get_document_count(
            db, tag.id, current_user.organization_id
        )
    return tag


@router.patch("/{id}", response_model=Tag)
async def update_tag(
    id: int,
    tag_in: TagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Rename a collection.
    - Only org-scoped collections can be renamed (not system/global ones).
    - Returns 409 if the new name already exists within the same org.
    """
    tag = await crud_tag.get(db, id)
    _assert_tag_exists(tag)
    _assert_org_owns_tag(tag, current_user)
    _assert_tag_is_editable(tag)

    # Only allow renaming — category is AI-assigned, not user-editable
    rename_only = TagUpdate(name=tag_in.name)

    try:
        updated = await crud_tag.update(db, id, rename_only)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A collection with this name already exists in your organisation",
        )

    if not hasattr(updated, "document_count"):
        updated.document_count = await crud_tag.get_document_count(
            db, updated.id, current_user.organization_id
        )
    return updated


@router.delete("/{id}", response_model=dict)
async def delete_tag(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Delete a collection.
    - Only org-scoped collections can be deleted (not system/global ones).
    - All document associations are removed automatically via CASCADE.
    - Returns the document count that was affected.
    """
    tag = await crud_tag.get(db, id)
    _assert_tag_exists(tag)
    _assert_org_owns_tag(tag, current_user)
    _assert_tag_is_editable(tag)

    # Get count before deletion so we can return it
    affected_count = await crud_tag.get_document_count(
        db, id, current_user.organization_id
    )

    await crud_tag.delete(db, id)

    return {"id": id, "affected_documents": affected_count}
