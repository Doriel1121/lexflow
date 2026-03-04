from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.audit_log import AuditLog
from app.db.models.user import User
from typing import Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)

async def log_audit(
    db: AsyncSession,
    user: User,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[AuditLog]:
    """
    Logs an action performed by a user to the audit_logs table.
    """
    try:
        audit_log = AuditLog(
            user_id=user.id,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)
        return audit_log
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        return None
