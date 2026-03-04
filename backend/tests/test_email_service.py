import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.email_service import email_service
from app.db.models.email_config import EmailConfig

@pytest.mark.asyncio
async def test_fetch_recent_emails_mock_imap():
    mock_db_session = AsyncMock() # Standalone mock
    # Mock EmailConfig
    config = EmailConfig(
        id=1, user_id=1, provider='imap', 
        email_address="test@example.com", 
        imap_server="imap.test.com", 
        encrypted_password="pass"
    )
    
    # Mock aioimaplib
    with patch('aioimaplib.IMAP4_SSL', new_callable=MagicMock) as mock_imap_cls:
        mock_client = AsyncMock()
        mock_imap_cls.return_value = mock_client
        
        # Mock login/select sequence
        mock_client.wait_hello_from_server.return_value = None
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'Selected'])
        
        # Mock search
        mock_client.search.return_value = ('OK', [b'1'])
        
        # Mock fetch
        # Email with attachment
        raw_email = b'Subject: Test Email\r\nContent-Type: multipart/mixed; boundary="boundary"\r\n\r\n--boundary\r\nContent-Disposition: attachment; filename="test.pdf"\r\n\r\nPDF_CONTENT\r\n--boundary--'
        mock_client.fetch.return_value = ('OK', [b'1 (RFC822 {100}', raw_email, b')'])
        
        # Mock SmartRouter to avoid DB calls inside it
        with patch('app.services.email_service.smart_router.route_document', new_callable=AsyncMock) as mock_route:
            mock_route.return_value = None
            
            # Mock Document CRUD
            with patch('app.crud.document.document_crud.create', new_callable=AsyncMock) as mock_create_doc:
                mock_create_doc.return_value = MagicMock(id=100)
                
                # Mock DB get user for audit
                mock_db_session.get = AsyncMock(return_value=MagicMock(id=1))
                
                # Mock audit log
                with patch('app.services.email_service.log_audit', new_callable=AsyncMock) as mock_audit:
                
                    await email_service.fetch_recent_emails(mock_db_session, config)
                    
                    # Verify interactions
                    mock_client.login.assert_called_with("test@example.com", "pass")
                    mock_create_doc.assert_called()
                    mock_audit.assert_called()
