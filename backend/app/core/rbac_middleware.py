"""
core/rbac_middleware.py
========================
Backend RBAC middleware that enforces system/tenant data separation
at the API layer — independent of frontend guards.

Defense-in-depth principle:
  Frontend guards protect the UI.
  This middleware protects the API.
  Both must agree. Neither trusts the other.

Rules enforced:
  - System Admin (role=ADMIN) is BLOCKED from all tenant data endpoints.
  - Tenant users are BLOCKED from all /admin/* endpoints
    (already handled by RoleChecker, but this adds a second layer).

Usage:
  Added to app in main.py via app.add_middleware(RBACMiddleware)
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Routes that System Admin must NEVER access ────────────────────────────
# These are tenant-data endpoints. A system admin calling these indicates
# either a bug or an attack attempt. Both are blocked and logged.

ADMIN_BLOCKED_PREFIXES = [
    "/api/v1/clients",
    "/api/v1/cases",
    "/api/v1/documents",
    "/api/v1/email",
    "/api/v1/collections",
    "/api/v1/tags",
    "/api/v1/deadlines",
    "/api/v1/risk",
    "/api/v1/search",
    "/api/v1/ai",
    "/api/v1/invitations",
    "/api/v1/notifications",
]

# ── Routes that Tenant users must NEVER access ────────────────────────────
# /admin/* is already protected by RoleChecker([UserRole.ADMIN]) on every
# endpoint, but we add middleware enforcement as a second layer.

TENANT_BLOCKED_PREFIXES = [
    "/api/v1/admin",
]

# ── Public routes (no auth, skip RBAC check) ─────────────────────────────
PUBLIC_PREFIXES = [
    "/token",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/uploads",
    "/",
]


class RBACMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces role-based access at the HTTP layer.

    Runs AFTER authentication middleware has set request.state.user.
    If no user is set (unauthenticated), skips RBAC checks
    (auth middleware handles 401 separately).
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip public routes
        if any(path == p or path.startswith(p) for p in PUBLIC_PREFIXES if p != "/"):
            return await call_next(request)

        user = getattr(request.state, "user", None)

        # No user in state = unauthenticated, let auth deps handle it
        if user is None:
            return await call_next(request)

        role = (user.role.value if hasattr(user.role, "value") else str(user.role)).lower()

        # ── System Admin trying to access tenant data endpoints ──────────
        if role == "admin":
            for prefix in ADMIN_BLOCKED_PREFIXES:
                if path.startswith(prefix):
                    logger.warning(
                        "RBAC VIOLATION: System Admin (user_id=%s) attempted "
                        "to access tenant endpoint %s %s — blocked",
                        user.id, request.method, path,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": (
                                "System Administrators cannot access tenant data endpoints. "
                                "Use the /api/v1/admin/* endpoints instead."
                            )
                        },
                    )

        # ── Tenant user trying to access admin endpoints ──────────────────
        if role != "admin":
            for prefix in TENANT_BLOCKED_PREFIXES:
                if path.startswith(prefix):
                    logger.warning(
                        "RBAC VIOLATION: Tenant user (user_id=%s, role=%s) attempted "
                        "to access admin endpoint %s %s — blocked",
                        user.id, role, request.method, path,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": (
                                "Access denied. This endpoint is restricted to system administrators."
                            )
                        },
                    )

        return await call_next(request)
