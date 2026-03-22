from fastapi import APIRouter

from app.api.v1.endpoints import (
    users, cases, documents, search, email, auth, organizations,
    admin, tags, invitations, risk, notifications, clients, deadlines, ai,
    org_analytics, intake
)

api_router_v1 = APIRouter()
api_router_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router_v1.include_router(users.router, prefix="/users", tags=["users"])
api_router_v1.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router_v1.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router_v1.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router_v1.include_router(search.router, prefix="/search", tags=["search"])
api_router_v1.include_router(email.router, prefix="/email", tags=["email"])
api_router_v1.include_router(intake.router, tags=["intake"])
api_router_v1.include_router(organizations.router, tags=["organizations"])
api_router_v1.include_router(admin.router, tags=["admin"])
api_router_v1.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router_v1.include_router(invitations.router, prefix="/invitations", tags=["invitations"])
api_router_v1.include_router(risk.router, prefix="/risk", tags=["risk"])
api_router_v1.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router_v1.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router_v1.include_router(deadlines.router, prefix="/deadlines", tags=["deadlines"])
api_router_v1.include_router(org_analytics.router, tags=["org-analytics"])
