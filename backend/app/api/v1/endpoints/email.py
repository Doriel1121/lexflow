"""
Email Endpoints
================
– Inbound webhook: POST /v1/email/inbound/{slug}   (public, HMAC-protected)
– Email config management: CRUD for user email accounts
– Legacy message listing (kept for UI compatibility)
"""
import email as email_lib
import hashlib
import hmac
import re
import secrets
from datetime import datetime
from email.header import decode_header
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user, RoleChecker
from app.db.models.email_config import EmailConfig, _generate_slug, _generate_secret
from app.db.models.email_message import EmailMessage
from app.db.models.user import User, UserRole
from app.schemas.email import EmailConfigCreate, EmailConfigResponse
from app.services.email_ingestion import email_ingestion_service

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INBOUND_DOMAIN = "inbound.lexflow.app"


def _decode_header_value(raw: str) -> str:
    """Decode RFC-2047 encoded email header to plain string."""
    parts = decode_header(raw or "")
    result = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            result.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(chunk)
    return "".join(result)


# ---------------------------------------------------------------------------
# ✅  PUBLIC WEBHOOK  — POST /v1/email/inbound/{slug}
# ---------------------------------------------------------------------------

@router.post("/inbound/{slug}", include_in_schema=True)
async def email_inbound_webhook(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Inbound email webhook — called by Postal / SendGrid / Mailgun when a
    new email arrives at <slug>@inbound.lexflow.app.

    Authentication: HMAC-SHA256 of the raw body with the config's webhook_secret,
    passed as the X-Webhook-Signature header  (hex-encoded).

    For local/development testing, if no signature header is present AND
    the APP_ENV is 'development', the check is skipped.
    """
    # 1. Look up config by slug
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.inbound_slug == slug, EmailConfig.is_active == True)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Inbound address not found")

    if not config.ingestion_enabled:
        return {"status": "ingestion_disabled"}

    # 2. Verify HMAC signature (skip in dev if no header provided)
    import os
    raw_body = await request.body()
    sig_header = request.headers.get("X-Webhook-Signature", "")
    is_dev = os.getenv("APP_ENV", "production").lower() == "development"

    if sig_header:
        expected = hmac.new(
            config.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header.lower()):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")
    elif not is_dev:
        raise HTTPException(status_code=403, detail="Missing webhook signature")

    # 3. Parse the inbound email
    #    Postal / SendGrid post as:  multipart/form-data with "message" (raw RFC-822)
    #    or as individual fields (from, subject, attachments[])
    #    We support both modes.

    content_type = request.headers.get("content-type", "")
    attachments = []
    email_from = ""
    email_subject = ""
    email_received_at = datetime.utcnow()

    if "multipart/form-data" in content_type:
        form = await request.form()

        # Mode A: raw RFC-822 message in a "message" field (Postal default)
        if "message" in form:
            raw_msg_field = form["message"]
            raw_bytes = (
                await raw_msg_field.read()
                if hasattr(raw_msg_field, "read")
                else raw_msg_field.encode()
            )
            msg = email_lib.message_from_bytes(raw_bytes)
            email_from = msg.get("From", "")
            email_subject = _decode_header_value(msg.get("Subject", ""))

            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                fname = part.get_filename()
                if fname:
                    attachments.append({
                        "filename": _decode_header_value(fname),
                        "content_type": part.get_content_type(),
                        "bytes": part.get_payload(decode=True) or b"",
                    })

        # Mode B: SendGrid / Mailgun style — separate form fields
        else:
            email_from = str(form.get("from", form.get("sender", "")))
            email_subject = str(form.get("subject", ""))
            # Attachments may be UploadFile objects
            idx = 1
            while f"attachment{idx}" in form:
                att = form[f"attachment{idx}"]
                if hasattr(att, "read"):
                    data = await att.read()
                    attachments.append({
                        "filename": att.filename or f"attachment{idx}",
                        "content_type": att.content_type or "application/octet-stream",
                        "bytes": data,
                    })
                idx += 1

    elif "application/json" in content_type:
        # Some providers POST JSON with base64-encoded attachments
        import json, base64
        payload = json.loads(raw_body)
        email_from = payload.get("from", "")
        email_subject = payload.get("subject", "")
        for att in payload.get("attachments", []):
            attachments.append({
                "filename": att.get("filename", "attachment.pdf"),
                "content_type": att.get("content-type", "application/pdf"),
                "bytes": base64.b64decode(att.get("content", "")),
            })

    if not attachments:
        return {"status": "no_attachments", "processed": 0}

    # 4. Run the ingestion pipeline for each attachment
    processed = 0
    skipped = 0
    for att in attachments:
        doc = await email_ingestion_service.process_attachment(
            db,
            config=config,
            filename=att["filename"],
            content_type=att["content_type"],
            file_bytes=att["bytes"],
            email_from=email_from,
            email_subject=email_subject,
            email_received_at=email_received_at,
        )
        if doc:
            processed += 1
        else:
            skipped += 1

    return {
        "status": "ok",
        "processed": processed,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Email Config CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[EmailConfigResponse])
async def get_email_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List email configs for the current user, including their inbound address."""
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    )
    configs = result.scalars().all()
    return configs


@router.post("/", response_model=EmailConfigResponse)
async def create_email_config(
    config_in: EmailConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])
    ),
):
    """
    Register an email address for inbound auto-ingestion.
    LexFlow generates a unique inbound address automatically — no credentials needed.
    """
    # Generate unique slug (retry if collision)
    for _ in range(5):
        slug = _generate_slug(config_in.email_address)
        existing = await db.execute(
            select(EmailConfig).where(EmailConfig.inbound_slug == slug)
        )
        if not existing.scalar_one_or_none():
            break

    config = EmailConfig(
        user_id=current_user.id,
        organization_id=getattr(current_user, "organization_id", None),
        email_address=config_in.email_address,
        provider="inbound",
        inbound_slug=slug,
        webhook_secret=_generate_secret(),
        is_active=True,
        ingestion_enabled=True,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}")
async def delete_email_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove an email config (disables the inbound address)."""
    config = await db.get(EmailConfig, config_id)
    if not config or config.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Email config not found")
    await db.delete(config)
    await db.commit()
    return {"status": "deleted"}


@router.patch("/{config_id}/toggle")
async def toggle_email_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Enable or disable ingestion for an email config."""
    config = await db.get(EmailConfig, config_id)
    if not config or config.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Email config not found")
    config.ingestion_enabled = not config.ingestion_enabled
    db.add(config)
    await db.commit()
    return {"ingestion_enabled": config.ingestion_enabled}


# ---------------------------------------------------------------------------
# Legacy message listing (kept for the Email Intake page UI)
# ---------------------------------------------------------------------------

@router.get("/messages")
async def get_all_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(list(UserRole))),
    limit: int = 50,
):
    """Email messages for the current user's configs."""
    user_config_ids_result = await db.execute(
        select(EmailConfig.id).where(EmailConfig.user_id == current_user.id)
    )
    config_ids = [c[0] for c in user_config_ids_result.all()]
    if not config_ids:
        return []

    query = (
        select(EmailMessage)
        .where(EmailMessage.email_config_id.in_(config_ids))
        .order_by(desc(EmailMessage.received_date))
        .limit(limit)
    )
    result = await db.execute(query)
    messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "from": m.from_address,
            "subject": m.subject,
            "text": m.body[:200] if m.body else "",
            "date": m.received_date.strftime("%Y-%m-%d %H:%M") if m.received_date else "Unknown",
            "unread": not m.is_read,
            "attachments": [f"attachment_{i}.pdf" for i in range(m.attachment_count)],
        }
        for m in messages
    ]
