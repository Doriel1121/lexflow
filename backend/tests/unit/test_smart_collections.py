"""
Unit tests for SmartCollectionsService.

These tests use mocked SQLAlchemy sessions and crud_tag to isolate
the routing logic from the database.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_document(doc_id: int = 1, org_id: int | None = 10):
    doc = MagicMock()
    doc.id = doc_id
    doc.organization_id = org_id
    doc.tags = []
    return doc


def _make_tag(tag_id: int, name: str, category: str):
    tag = MagicMock()
    tag.id = tag_id
    tag.name = name
    tag.category = category
    return tag


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_routes_client_id_from_party_id_number():
    """A party with an id_number should create a 'client_id' tag."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [{"name": "John Doe", "role": "Buyer", "id_number": "123456789"}],
        "document_type": "",
        "document_subtype": "",
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    tag = _make_tag(1, "123456789", "client_id")

    # Patch Document reload
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = _make_document()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(return_value=tag)
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        mock_crud.find_or_create.assert_any_call(
            db, name="123456789", category="client_id", organization_id=10
        )


@pytest.mark.asyncio
async def test_routes_organization_from_company_party():
    """A party name ending in a company suffix should create an 'organization' tag."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [{"name": "Acme Corp Ltd", "role": "Seller", "id_number": None}],
        "document_type": "",
        "document_subtype": "",
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    tag = _make_tag(2, "Acme Corp Ltd", "organization")

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = _make_document()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(return_value=tag)
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        mock_crud.find_or_create.assert_any_call(
            db, name="Acme Corp Ltd", category="organization", organization_id=10
        )


@pytest.mark.asyncio
async def test_routes_case_type_from_document_type():
    """document_type in AI result should map to a 'case_type' collection."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [],
        "document_type": "Contract",
        "document_subtype": "",
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    tag = _make_tag(3, "Contract", "case_type")

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = _make_document()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(return_value=tag)
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        mock_crud.find_or_create.assert_any_call(
            db, name="Contract", category="case_type", organization_id=10
        )


@pytest.mark.asyncio
async def test_routes_document_subtype():
    """document_subtype in AI result should map to a 'document_type' collection."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [],
        "document_type": "Contract",
        "document_subtype": "NDA",
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    tag_ct = _make_tag(3, "Contract", "case_type")
    tag_dt = _make_tag(4, "NDA", "document_type")

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = _make_document()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(side_effect=[tag_ct, tag_dt])
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        mock_crud.find_or_create.assert_any_call(
            db, name="NDA", category="document_type", organization_id=10
        )


@pytest.mark.asyncio
async def test_no_duplicate_tags_added():
    """If the document already has the tag, it should not be appended again."""
    from app.services.smart_collections import SmartCollectionsService

    tag = _make_tag(5, "Contract", "case_type")

    ai_analysis = {
        "parties": [],
        "document_type": "Contract",
        "document_subtype": "",
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    # Document already has this tag
    doc_with_tag = _make_document()
    doc_with_tag.tags = [tag]

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = doc_with_tag
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(return_value=tag)
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        # commit should NOT have been called because nothing new was added
        db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_empty_ai_analysis_no_crash():
    """An empty AI analysis dict should not raise or create any tags."""
    from app.services.smart_collections import SmartCollectionsService

    svc = SmartCollectionsService()
    db = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock()
        # Should not raise
        await svc.route_document_to_collections(db, _make_document(), {})
        mock_crud.find_or_create.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_document_type_skipped():
    """'Unknown' document_type should NOT create a collection."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [],
        "document_type": "Unknown",
        "document_subtype": "Unclassified",
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock()
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        mock_crud.find_or_create.assert_not_called()


@pytest.mark.asyncio
async def test_routing_ids_from_ai_analysis():
    """routing_ids list (from MetadataExtractionService) should produce client_id tags."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [],
        "document_type": "",
        "document_subtype": "",
        "routing_ids": ["987654321"],
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    tag = _make_tag(6, "987654321", "client_id")

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = _make_document()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(return_value=tag)
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        mock_crud.find_or_create.assert_any_call(
            db, name="987654321", category="client_id", organization_id=10
        )


@pytest.mark.asyncio
async def test_ai_tags_field():
    """Generic 'tags' list from AI analysis should produce 'ai_tag' collections."""
    from app.services.smart_collections import SmartCollectionsService

    ai_analysis = {
        "parties": [],
        "document_type": "",
        "document_subtype": "",
        "tags": ["Urgent", "Litigation"],
    }

    svc = SmartCollectionsService()
    db = AsyncMock()

    tag1 = _make_tag(7, "Urgent", "ai_tag")
    tag2 = _make_tag(8, "Litigation", "ai_tag")

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = _make_document()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with patch("app.services.smart_collections.crud_tag") as mock_crud:
        mock_crud.find_or_create = AsyncMock(side_effect=[tag1, tag2])
        await svc.route_document_to_collections(db, _make_document(), ai_analysis)
        
        mock_crud.find_or_create.assert_any_call(
            db, name="Urgent", category="ai_tag", organization_id=10
        )
        mock_crud.find_or_create.assert_any_call(
            db, name="Litigation", category="ai_tag", organization_id=10
        )
