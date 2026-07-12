import pytest
from unittest.mock import AsyncMock

from app.db.models.case import Case
from app.services.case_suggestion import CaseSuggestion
from app.services.smart_router import smart_router


@pytest.mark.asyncio
async def test_route_document_high_confidence_suggestion(monkeypatch):
    mock_db = AsyncMock()
    mock_case = Case(id=123, title="Test Case")
    mock_db.get.return_value = mock_case

    suggest_case = AsyncMock(
        return_value=CaseSuggestion(
            case_id=123,
            case_title="Test Case",
            reason="Case #123 found in subject/content",
            confidence="high",
        )
    )
    monkeypatch.setattr(
        "app.services.smart_router.case_suggestion_service.suggest_case",
        suggest_case,
    )

    matched_case = await smart_router.route_document(
        mock_db,
        "This is a document for Case #123 regarding the merger.",
        metadata={"organization_id": 7},
    )

    assert matched_case is mock_case
    suggest_case.assert_awaited_once_with(
        mock_db,
        search_text="This is a document for Case #123 regarding the merger.",
        org_id=7,
    )
    mock_db.get.assert_awaited_once_with(Case, 123)


@pytest.mark.asyncio
async def test_route_document_no_suggestion(monkeypatch):
    mock_db = AsyncMock()
    suggest_case = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.smart_router.case_suggestion_service.suggest_case",
        suggest_case,
    )

    matched_case = await smart_router.route_document(
        mock_db,
        "This is a generic document with no case ID.",
    )

    assert matched_case is None
    mock_db.get.assert_not_called()


@pytest.mark.asyncio
async def test_route_document_ignores_low_confidence_suggestion(monkeypatch):
    mock_db = AsyncMock()
    suggest_case = AsyncMock(
        return_value=CaseSuggestion(
            case_id=456,
            case_title="Possible Case",
            reason="Keyword match",
            confidence="low",
        )
    )
    monkeypatch.setattr(
        "app.services.smart_router.case_suggestion_service.suggest_case",
        suggest_case,
    )

    matched_case = await smart_router.route_document(
        mock_db,
        "Possible keyword-only match.",
    )

    assert matched_case is None
    mock_db.get.assert_not_called()
