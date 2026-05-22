"""
Unit tests for the refactored CRUDTag.

All DB interactions are mocked — no real database required.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.exc import IntegrityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tag(tag_id: int, name: str, category: str, org_id: int | None = None):
    tag = MagicMock()
    tag.id = tag_id
    tag.name = name
    tag.category = category
    tag.organization_id = org_id
    tag.document_count = 0
    return tag


def _make_db(execute_return=None):
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = execute_return
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# find_or_create — global const path (case_type, document_type)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_or_create_global_returns_existing():
    """Global const tag found by (name, category) — no new row created."""
    from app.crud.tag import CRUDTag

    existing = _make_tag(1, "Contract", "case_type", org_id=None)
    crud = CRUDTag()

    with patch.object(crud, "get_global_by_name_and_category", AsyncMock(return_value=existing)):
        result = await crud.find_or_create(AsyncMock(), "Contract", "case_type", organization_id=5)

    assert result is existing


@pytest.mark.asyncio
async def test_find_or_create_global_creates_when_missing():
    """Global const tag not found — creates with organization_id=None."""
    from app.crud.tag import CRUDTag

    crud = CRUDTag()
    db = _make_db()

    with patch.object(crud, "get_global_by_name_and_category", AsyncMock(return_value=None)):
        result = await crud.find_or_create(db, "NDA", "document_type", organization_id=5)

    db.add.assert_called_once()
    added_tag = db.add.call_args[0][0]
    assert added_tag.name == "NDA"
    assert added_tag.category == "document_type"
    assert added_tag.organization_id is None  # must be global


@pytest.mark.asyncio
async def test_find_or_create_global_race_condition():
    """IntegrityError on global create → fetches the winner row."""
    from app.crud.tag import CRUDTag

    winner = _make_tag(2, "NDA", "document_type", org_id=None)
    crud = CRUDTag()
    db = _make_db()
    db.commit = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

    with patch.object(crud, "get_global_by_name_and_category",
                      AsyncMock(side_effect=[None, winner])):
        result = await crud.find_or_create(db, "NDA", "document_type", organization_id=5)

    db.rollback.assert_called_once()
    assert result is winner


# ---------------------------------------------------------------------------
# find_or_create — org-scoped path (client_id, organization, project, ai_tag)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_or_create_org_scoped_returns_existing():
    """Org-scoped tag found by (name, org_id) — no new row created."""
    from app.crud.tag import CRUDTag

    existing = _make_tag(3, "512345678", "client_id", org_id=10)
    crud = CRUDTag()

    with patch.object(crud, "get_by_name_and_org", AsyncMock(return_value=existing)):
        result = await crud.find_or_create(AsyncMock(), "512345678", "client_id", organization_id=10)

    assert result is existing


@pytest.mark.asyncio
async def test_find_or_create_org_scoped_creates_when_missing():
    """Org-scoped tag not found — creates with correct organization_id."""
    from app.crud.tag import CRUDTag

    crud = CRUDTag()
    db = _make_db()

    with patch.object(crud, "get_by_name_and_org", AsyncMock(return_value=None)):
        await crud.find_or_create(db, "Acme Ltd", "organization", organization_id=10)

    db.add.assert_called_once()
    added_tag = db.add.call_args[0][0]
    assert added_tag.name == "Acme Ltd"
    assert added_tag.category == "organization"
    assert added_tag.organization_id == 10  # must be org-scoped


@pytest.mark.asyncio
async def test_find_or_create_org_scoped_never_crosses_orgs():
    """
    Org 10 creates 'Acme Ltd'. Org 20 should get its own separate tag,
    not reuse Org 10's tag.
    """
    from app.crud.tag import CRUDTag

    crud = CRUDTag()
    db_org10 = _make_db()
    db_org20 = _make_db()

    tag_org10 = _make_tag(3, "Acme Ltd", "organization", org_id=10)
    tag_org20 = _make_tag(4, "Acme Ltd", "organization", org_id=20)

    # Org 10 finds its own tag
    with patch.object(crud, "get_by_name_and_org", AsyncMock(return_value=tag_org10)):
        result_10 = await crud.find_or_create(db_org10, "Acme Ltd", "organization", organization_id=10)

    # Org 20 finds its own tag (different row)
    with patch.object(crud, "get_by_name_and_org", AsyncMock(return_value=tag_org20)):
        result_20 = await crud.find_or_create(db_org20, "Acme Ltd", "organization", organization_id=20)

    assert result_10.organization_id == 10
    assert result_20.organization_id == 20
    assert result_10.id != result_20.id


@pytest.mark.asyncio
async def test_find_or_create_org_scoped_race_condition():
    """IntegrityError on org-scoped create → fetches the winner row."""
    from app.crud.tag import CRUDTag

    winner = _make_tag(5, "Project Alpha", "project", org_id=10)
    crud = CRUDTag()
    db = _make_db()
    db.commit = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

    with patch.object(crud, "get_by_name_and_org",
                      AsyncMock(side_effect=[None, winner])):
        result = await crud.find_or_create(db, "Project Alpha", "project", organization_id=10)

    db.rollback.assert_called_once()
    assert result is winner


@pytest.mark.asyncio
async def test_find_or_create_org_scoped_updates_category():
    """If tag exists but category is less specific, update it."""
    from app.crud.tag import CRUDTag

    existing = _make_tag(6, "Acme Ltd", "ai_tag", org_id=10)
    crud = CRUDTag()
    db = _make_db()

    with patch.object(crud, "get_by_name_and_org", AsyncMock(return_value=existing)):
        await crud.find_or_create(db, "Acme Ltd", "organization", organization_id=10)

    # Category should have been updated to the more specific one
    assert existing.category == "organization"
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# update — IntegrityError on name conflict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_raises_integrity_error_on_name_conflict():
    """Renaming to an existing name within the same org raises IntegrityError."""
    from app.crud.tag import CRUDTag

    existing = _make_tag(7, "Old Name", "organization", org_id=10)
    crud = CRUDTag()
    db = _make_db(execute_return=existing)
    db.commit = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

    from app.schemas.tag import TagUpdate
    with pytest.raises(IntegrityError):
        await crud.update(db, 7, TagUpdate(name="Existing Name"))

    db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_update_returns_none_when_tag_not_found():
    """update() returns None if tag_id doesn't exist."""
    from app.crud.tag import CRUDTag

    crud = CRUDTag()
    db = _make_db(execute_return=None)

    from app.schemas.tag import TagUpdate
    result = await crud.update(db, 999, TagUpdate(name="New Name"))
    assert result is None


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_returns_none_when_not_found():
    """delete() returns None if tag_id doesn't exist."""
    from app.crud.tag import CRUDTag

    crud = CRUDTag()
    db = _make_db(execute_return=None)

    result = await crud.delete(db, 999)
    assert result is None
    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_removes_tag():
    """delete() calls db.delete and commits."""
    from app.crud.tag import CRUDTag

    tag = _make_tag(8, "Acme Ltd", "organization", org_id=10)
    crud = CRUDTag()
    db = _make_db(execute_return=tag)

    result = await crud.delete(db, 8)

    assert result is tag
    db.delete.assert_called_once_with(tag)
    db.commit.assert_called_once()
