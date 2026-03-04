import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.audit import log_audit
from app.db.models.user import User

@pytest.mark.asyncio
async def test_log_audit_success():
    # Mock DB session
    mock_db = AsyncMock()
    
    # Mock User
    mock_user = User(id=1, email="test@example.com")
    
    # Call service
    await log_audit(
        db=mock_db,
        user=mock_user,
        action="test_action",
        details={"foo": "bar"},
        ip_address="127.0.0.1",
        user_agent="pytest"
    )
    
    # Verify DB add and commit called
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()
    
    # Verify call args
    call_args = mock_db.add.call_args
    audit_log = call_args[0][0]
    assert audit_log.user_id == 1
    assert audit_log.action == "test_action"
    assert audit_log.details == {"foo": "bar"}
    assert audit_log.ip_address == "127.0.0.1"
