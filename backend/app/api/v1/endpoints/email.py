from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
import httpx
import base64

from app.core.dependencies import get_db, get_current_active_user, RoleChecker
from app.db.models.user import User, UserRole
from app.db.models.email_config import EmailConfig
from app.db.models.email_message import EmailMessage
from app.schemas.email import EmailConfigCreate, EmailConfigResponse

router = APIRouter()

@router.get("/", response_model=List[EmailConfigResponse])
async def get_email_configs(
    db: AsyncSession = Depends(get_db)
):
    """Get configured email accounts."""
    result = await db.execute(select(EmailConfig))
    configs = result.scalars().all()
    return configs

@router.post("/", response_model=EmailConfigResponse)
async def create_email_config(
    config_in: EmailConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """Add a new email account configuration."""
    config = EmailConfig(
        user_id=current_user.id,
        email_address=config_in.email_address,
        provider=config_in.provider,
        imap_server=config_in.imap_server,
        imap_port=config_in.imap_port,
        username=config_in.username,
        password=config_in.password,
        is_active=True
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config

@router.get("/messages")
async def get_all_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(list(UserRole))),
    limit: int = 50
):
    """
    Get email messages filtered by user.
    """
    # Get user's email configs
    user_configs = await db.execute(
        select(EmailConfig.id).where(EmailConfig.user_id == current_user.id)
    )
    config_ids = [c[0] for c in user_configs.all()]
    
    if not config_ids:
        # No configs, return empty
        return []
    
    # Get messages for user's configs
    query = select(EmailMessage).where(
        EmailMessage.email_config_id.in_(config_ids)
    ).order_by(desc(EmailMessage.received_date)).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return [{
        "id": m.id,
        "from": m.from_address,
        "subject": m.subject,
        "text": m.body[:200] if m.body else "",
        "date": m.received_date.strftime("%Y-%m-%d %H:%M") if m.received_date else "Unknown",
        "unread": not m.is_read,
        "attachments": [f"attachment_{i}.pdf" for i in range(m.attachment_count)]
    } for m in messages]

@router.post("/sync-gmail")
async def sync_gmail(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """Sync emails from Gmail using OAuth token."""
    
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=400, 
            detail="Gmail not connected. Please login with Google."
        )
    
    # Get or create email config for this user
    result = await db.execute(
        select(EmailConfig).where(
            EmailConfig.user_id == current_user.id,
            EmailConfig.provider == "gmail"
        )
    )
    email_config = result.scalar_one_or_none()
    
    if not email_config:
        email_config = EmailConfig(
            user_id=current_user.id,
            email_address=current_user.email,
            provider="gmail",
            is_active=True
        )
        db.add(email_config)
        await db.commit()
        await db.refresh(email_config)
    
    try:
        async with httpx.AsyncClient() as client:
            # Fetch recent messages from primary inbox only (exclude promotions, social, updates)
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {current_user.google_access_token}"},
                params={"maxResults": 10, "q": "in:inbox category:primary"}
            )
            
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Gmail token expired. Please login again.")
            
            messages_data = response.json()
            new_messages = []
            
            # Fetch full message details
            for msg in messages_data.get("messages", [])[:10]:
                msg_response = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                    headers={"Authorization": f"Bearer {current_user.google_access_token}"}
                )
                msg_data = msg_response.json()
                
                # Extract headers
                headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                
                # Get body
                body = msg_data.get("snippet", "")
                
                # Check if already exists
                existing = await db.execute(
                    select(EmailMessage).where(EmailMessage.message_id == msg_data["id"])
                )
                if existing.scalar_one_or_none():
                    continue
                
                # Save to database with email_config_id
                email_message = EmailMessage(
                    email_config_id=email_config.id,
                    message_id=msg_data["id"],
                    from_address=headers.get("From", ""),
                    to_address=headers.get("To", ""),
                    subject=headers.get("Subject", "(No Subject)"),
                    body=body,
                    received_date=datetime.fromtimestamp(int(msg_data["internalDate"]) / 1000),
                    is_read=False,
                    has_attachments="parts" in msg_data.get("payload", {}),
                    attachment_count=len([p for p in msg_data.get("payload", {}).get("parts", []) if p.get("filename")])
                )
                db.add(email_message)
                new_messages.append(email_message)
            
            await db.commit()
            
            return {"status": "success", "new_messages": len(new_messages)}
    
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Gmail API error: {str(e)}")


@router.post("/{config_id}/sync")
async def sync_email_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """Trigger email sync and store messages."""
    config = await db.get(EmailConfig, config_id)
    if not config or config.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Email config not found")
    
    # Simulate fetching emails (in production, use actual IMAP/Graph API)
    new_messages = []
    for i in range(3):
        message = EmailMessage(
            email_config_id=config_id,
            message_id=f"msg_{datetime.utcnow().timestamp()}_{i}",
            from_address=f"client{i}@example.com",
            to_address=config.email_address,
            subject=f"Legal Document Request #{i+1}",
            body=f"Dear Counsel, Please review the attached documents for case #{i+1}.",
            received_date=datetime.utcnow(),
            is_read=False,
            has_attachments=True,
            attachment_count=2
        )
        db.add(message)
        new_messages.append(message)
    
    config.last_synced_at = datetime.utcnow()
    await db.commit()
    
    return {"status": "success", "new_messages": len(new_messages)}
