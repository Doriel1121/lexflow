from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.session import AsyncSessionLocal
from app.services.audit import log_audit
import logging
import json

logger = logging.getLogger(__name__)

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Process the request first
        response = await call_next(request)
        
        # We only log state-changing methods
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            # Retrieve the authenticated user attached by the dependency
            user = getattr(request.state, "user", None)
            
            if user:
                # Synchronously write the audit log to ensure data persistence
                try:
                    # Optional: We could read request body here, but it's consumed. 
                    # For minimal intrusion, we just log the endpoint details.
                    async with AsyncSessionLocal() as db:
                        await log_audit(
                            db=db,
                            event_type=f"{request.method}_{request.url.path.strip('/').replace('/', '_')}",
                            organization_id=user.organization_id,
                            user_id=user.id,
                            resource_type="endpoint",
                            resource_id=None,
                            http_method=request.method,
                            path=request.url.path,
                            status_code=response.status_code,
                            ip_address=request.client.host if request.client else None,
                            user_agent=request.headers.get("user-agent"),
                            metadata_json={"query_params": dict(request.query_params)}
                        )
                except Exception as e:
                    logger.error(f"AuditMiddleware synchronous logging failed: {e}")
                    
        return response
