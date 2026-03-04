import asyncio
import email
from email.header import decode_header
import aioimaplib
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.email_config import EmailConfig
from app.db.models.document import Document
from app.crud.document import document_crud
from app.schemas.document import DocumentCreate
from app.services.audit import log_audit
from app.db.models.user import User
from app.services.smart_router import smart_router
from app.services.storage import storage_service
import logging

logger = logging.getLogger(__name__)

class EmailService:
    async def fetch_recent_emails(self, db: AsyncSession, config: EmailConfig):
        if config.provider != 'imap':
            logger.warning(f"Provider {config.provider} not supported yet for {config.email_address}")
            return

        try:
            imap_client = aioimaplib.IMAP4_SSL(host=config.imap_server, port=config.imap_port)
            await imap_client.wait_hello_from_server()
            
            # TODO: Decrypt password
            password = config.encrypted_password # Placeholder
            
            await imap_client.login(config.email_address, password)
            await imap_client.select('INBOX')
            
            # Search UNSEEN messages
            typ, data = await imap_client.search('UNSEEN')
            if typ != 'OK':
                logger.error("Error searching emails")
                return

            processed_count = 0
            for num in data[0].split():
                typ, msg_data = await imap_client.fetch(num, '(RFC822)')
                if typ != 'OK':
                    continue

                raw_email = msg_data[1]
                msg = email.message_from_bytes(raw_email)
                
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                from_addr = msg.get("From", "unknown@unknown.com")
                logger.info(f"Processing email from {from_addr}: {subject}")
                
                # Check for attachments
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    
                    filename = part.get_filename()
                    if filename:
                        try:
                            # Download attachment
                            content = part.get_payload(decode=True)
                            
                            if not content:
                                logger.warning(f"Empty attachment: {filename}")
                                continue
                            
                            # Save to temp folder first
                            file_path_str, s3_url = await storage_service.save_file_bytes(
                                content, 
                                "temp", 
                                filename
                            )
                            
                            logger.info(f"Saved attachment {filename} to {file_path_str}")
                            
                            # Extract text content for routing
                            text_content = ""
                            if isinstance(content, bytes):
                                try:
                                    text_content = content.decode('utf-8', errors='ignore')
                                except:
                                    text_content = str(content)
                            elif isinstance(content, str):
                                text_content = content
                                
                            # Smart Routing
                            case_id = 0  # Default Inbox (unclassified)
                            matched_case = await smart_router.route_document(
                                db, 
                                content=f"{subject} {from_addr} {text_content[:1000]}"
                            )
                            
                            if matched_case:
                                case_id = matched_case.id
                                logger.info(f"Smart routed email attachment to case {case_id}")
                                
                                # Move file to case folder
                                case_folder = f"cases/{case_id}/attachments"
                                s3_url = await storage_service.move_file(f"temp/{filename}", case_folder)
                            else:
                                # Move to inbox/processed
                                s3_url = await storage_service.move_file(f"temp/{filename}", "inbox/processed")

                            # Create document record
                            doc_in = DocumentCreate(
                                filename=filename,
                                s3_url=s3_url,
                                case_id=case_id,
                                content=f"Email attachment from: {from_addr}\nSubject: {subject}\n\n{text_content[:500]}...",
                                classification="email_attachment",
                                language="en",
                                page_count=1
                            )
                            
                            new_doc = await document_crud.create(db, doc_in, owner_id=config.user_id)
                            logger.info(f"Created document {new_doc.id} for attachment {filename}")
                            
                            # Audit Log
                            user = await db.get(User, config.user_id)
                            if user:
                                await log_audit(
                                    db, 
                                    user, 
                                    "email_attachment_import", 
                                    {
                                        "email_subject": subject, 
                                        "filename": filename, 
                                        "document_id": new_doc.id,
                                        "from": from_addr
                                    }
                                )
                            
                            processed_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing attachment {filename}: {e}", exc_info=True)
                            continue
            
            await imap_client.logout()
            
            # Update last_synced_at
            config.last_synced_at = datetime.utcnow().isoformat()
            db.add(config)
            await db.commit()
            
            logger.info(f"Email sync completed for {config.email_address}: {processed_count} attachments processed")

        except Exception as e:
            logger.error(f"Error fetching emails for {config.email_address}: {e}", exc_info=True)

email_service = EmailService()
