import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.smart_router import smart_router
from app.db.models.case import Case

@pytest.mark.asyncio
async def test_route_document_regex_match():
    mock_db = AsyncMock()
    
    # Mock finding a case
    mock_case = Case(id=123, title="Test Case")
    mock_db.get.return_value = mock_case
    
    content = "This is a document for Case #123 regarding the merger."
    
    matched_case = await smart_router.route_document(mock_db, content)
    
    assert matched_case is not None
    assert matched_case.id == 123
    mock_db.get.assert_called_with(Case, 123)

@pytest.mark.asyncio
async def test_route_document_no_match():
    mock_db = AsyncMock()
    
    content = "This is a generic document with no case ID."
    
    # Mock llm_service to prevent actual API call if it wasn't mocked in smart_router
    # But smart_router imports it from app.services.llm
    # We should mock it.
    from app.services.smart_router import llm_service
    llm_service.extract_keywords = AsyncMock(return_value=["generic", "document"])
    
    matched_case = await smart_router.route_document(mock_db, content)
    
    assert matched_case is None
