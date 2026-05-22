"""
Integration tests for the tags API endpoints.

Tests PATCH /v1/tags/{id} and DELETE /v1/tags/{id} covering:
  - 404 not found
  - 403 cross-org access
  - 403 system (global const) tag protection
  - 409 name conflict within same org
  - 200 successful rename
  - 200 successful delete with correct affected_documents count
  - Data isolation: org A cannot see org B's document counts
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from app.schemas.tag import TagUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tag(tag_id: int, name: str, category: str, org_id: int | None):
    tag = MagicMock()
    tag.id = tag_id
    tag.name = name
    tag.category = category
    tag.organization_id = org_id
    tag.document_count = 0
    return tag


def _make_user(org_id: int, is_superuser: bool = False):
    user = MagicMock()
    user.organization_id = org_id
    user.is_superuser = is_superuser
    return user


# ---------------------------------------------------------------------------
# PATCH /v1/tags/{id}  — rename
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_tag_not_found():
    """Returns 404 when tag does not exist."""
    from app.api.v1.endpoints.tags import update_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await update_tag(id=999, tag_in=TagUpdate(name="New"), db=db, current_user=user)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_tag_cross_org_forbidden():
    """Returns 403 when tag belongs to a different org."""
    from app.api.v1.endpoints.tags import update_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(1, "Acme", "organization", org_id=20)  # different org

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)

        with pytest.raises(HTTPException) as exc:
            await update_tag(id=1, tag_in=TagUpdate(name="New"), db=db, current_user=user)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_patch_system_tag_forbidden():
    """Returns 403 when trying to rename a global const (system) tag."""
    from app.api.v1.endpoints.tags import update_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(2, "Contract", "case_type", org_id=None)  # global const

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)

        with pytest.raises(HTTPException) as exc:
            await update_tag(id=2, tag_in=TagUpdate(name="New"), db=db, current_user=user)

    assert exc.value.status_code == 403
    assert "System" in exc.value.detail


@pytest.mark.asyncio
async def test_patch_tag_name_conflict_returns_409():
    """Returns 409 when new name already exists in the same org."""
    from app.api.v1.endpoints.tags import update_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(3, "Old Name", "organization", org_id=10)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)
        mock_crud.update = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

        with pytest.raises(HTTPException) as exc:
            await update_tag(id=3, tag_in=TagUpdate(name="Existing Name"), db=db, current_user=user)

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_patch_tag_success():
    """Successfully renames an org-scoped tag."""
    from app.api.v1.endpoints.tags import update_tag

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(4, "Old Name", "organization", org_id=10)
    updated_tag = _make_tag(4, "New Name", "organization", org_id=10)
    updated_tag.document_count = 3

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)
        mock_crud.update = AsyncMock(return_value=updated_tag)
        mock_crud.get_document_count = AsyncMock(return_value=3)

        result = await update_tag(id=4, tag_in=TagUpdate(name="New Name"), db=db, current_user=user)

    assert result.name == "New Name"
    assert result.document_count == 3


@pytest.mark.asyncio
async def test_patch_tag_only_renames_not_category():
    """PATCH must only update name — category must not be changed by user."""
    from app.api.v1.endpoints.tags import update_tag

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(5, "Old", "organization", org_id=10)
    updated_tag = _make_tag(5, "New", "organization", org_id=10)
    updated_tag.document_count = 0

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)
        mock_crud.update = AsyncMock(return_value=updated_tag)
        mock_crud.get_document_count = AsyncMock(return_value=0)

        # Even if caller sends a category, it must be stripped
        await update_tag(
            id=5,
            tag_in=TagUpdate(name="New", category="client_id"),  # category injection attempt
            db=db,
            current_user=user,
        )

    # Verify update was called with name-only TagUpdate
    call_args = mock_crud.update.call_args
    tag_in_passed: TagUpdate = call_args[0][2]
    assert tag_in_passed.name == "New"
    assert tag_in_passed.category is None


# ---------------------------------------------------------------------------
# DELETE /v1/tags/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_tag_not_found():
    """Returns 404 when tag does not exist."""
    from app.api.v1.endpoints.tags import delete_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await delete_tag(id=999, db=db, current_user=user)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_tag_cross_org_forbidden():
    """Returns 403 when tag belongs to a different org."""
    from app.api.v1.endpoints.tags import delete_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(1, "Acme", "organization", org_id=20)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)

        with pytest.raises(HTTPException) as exc:
            await delete_tag(id=1, db=db, current_user=user)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_system_tag_forbidden():
    """Returns 403 when trying to delete a global const (system) tag."""
    from app.api.v1.endpoints.tags import delete_tag
    from fastapi import HTTPException

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(2, "NDA", "document_type", org_id=None)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)

        with pytest.raises(HTTPException) as exc:
            await delete_tag(id=2, db=db, current_user=user)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_tag_returns_affected_document_count():
    """DELETE returns the number of documents that had this tag removed."""
    from app.api.v1.endpoints.tags import delete_tag

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(3, "Acme Ltd", "organization", org_id=10)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)
        mock_crud.get_document_count = AsyncMock(return_value=7)
        mock_crud.delete = AsyncMock(return_value=tag)

        result = await delete_tag(id=3, db=db, current_user=user)

    assert result["id"] == 3
    assert result["affected_documents"] == 7
    mock_crud.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_tag_zero_documents():
    """DELETE with no linked documents returns affected_documents=0."""
    from app.api.v1.endpoints.tags import delete_tag

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(4, "Empty Tag", "project", org_id=10)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)
        mock_crud.get_document_count = AsyncMock(return_value=0)
        mock_crud.delete = AsyncMock(return_value=tag)

        result = await delete_tag(id=4, db=db, current_user=user)

    assert result["affected_documents"] == 0


@pytest.mark.asyncio
async def test_delete_document_count_scoped_to_org():
    """
    Document count must only count documents from the requesting org,
    not from all orgs that share the tag.
    """
    from app.api.v1.endpoints.tags import delete_tag

    db = AsyncMock()
    user = _make_user(org_id=10)
    tag = _make_tag(5, "Shared Name", "organization", org_id=10)

    with patch("app.api.v1.endpoints.tags.crud_tag") as mock_crud:
        mock_crud.get = AsyncMock(return_value=tag)
        mock_crud.get_document_count = AsyncMock(return_value=2)
        mock_crud.delete = AsyncMock(return_value=tag)

        await delete_tag(id=5, db=db, current_user=user)

    # Verify get_document_count was called with the correct org_id
    mock_crud.get_document_count.assert_called_once_with(db, 5, 10)
