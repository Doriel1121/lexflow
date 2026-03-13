import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.audit_log import AuditLog
from typing import Optional, Any, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def compute_audit_hash(
    organization_id: Any,
    user_id: Any,
    event_type: Any,
    resource_type: Any,
    resource_id: Any,
    http_method: Any,
    path: Any,
    status_code: Any,
    timestamp_iso: str,
    previous_hash: str
) -> str:
    parts = [
        str(organization_id) if organization_id is not None else "",
        str(user_id) if user_id is not None else "",
        str(event_type) if event_type is not None else "",
        str(resource_type) if resource_type is not None else "",
        str(resource_id) if resource_id is not None else "",
        str(http_method) if http_method is not None else "",
        str(path) if path is not None else "",
        str(status_code) if status_code is not None else "",
        str(timestamp_iso),
        str(previous_hash)
    ]
    raw_string = "|".join(parts)
    return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

async def log_audit(
    db: AsyncSession,
    event_type: str,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    http_method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata_json: Optional[Dict[str, Any]] = None
) -> Optional[AuditLog]:
    """
    Logs an action to the audit chain with tamper-evident hashing.
    """
    previous_hash = "GENESIS"
    if organization_id is not None:
        stmt = select(AuditLog).where(AuditLog.organization_id == organization_id).order_by(AuditLog.timestamp.desc()).limit(1)
        result = await db.execute(stmt)
        last_log = result.scalars().first()
        if last_log and last_log.hash:
            previous_hash = last_log.hash
            
    now = datetime.utcnow()
    timestamp_iso = now.isoformat()
    
    current_hash = compute_audit_hash(
        organization_id=organization_id,
        user_id=user_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        http_method=http_method,
        path=path,
        status_code=status_code,
        timestamp_iso=timestamp_iso,
        previous_hash=previous_hash
    )

    audit_log = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        http_method=http_method,
        path=path,
        status_code=status_code,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=metadata_json,
        timestamp=now,
        previous_hash=previous_hash,
        hash=current_hash
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(audit_log)
    return audit_log

async def verify_audit_chain(db: AsyncSession, organization_id: int) -> bool:
    """
    Verifies the cryptographic integrity of the audit log chain for an organization.
    """
    try:
        stmt = select(AuditLog).where(AuditLog.organization_id == organization_id).order_by(AuditLog.timestamp.asc())
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        expected_previous = "GENESIS"
        for log in logs:
            if log.previous_hash != expected_previous:
                logger.error(f"Chain broken at log {log.id}: expected {expected_previous}, got {log.previous_hash}")
                return False
                
            computed_hash = compute_audit_hash(
                organization_id=log.organization_id,
                user_id=log.user_id,
                event_type=log.event_type,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                http_method=log.http_method,
                path=log.path,
                status_code=log.status_code,
                timestamp_iso=log.timestamp.isoformat(),
                previous_hash=log.previous_hash
            )
            
            if computed_hash != log.hash:
                logger.error(f"Hash mismatch at log {log.id}: computed {computed_hash}, stored {log.hash}")
                return False
                
            expected_previous = log.hash
            
        return True
    except Exception as e:
        logger.error(f"Chain verification failed for org {organization_id}: {e}")
        return False

