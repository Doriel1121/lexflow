from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import timedelta
import asyncio
from pathlib import Path

from app.db.session import engine, Base, AsyncSessionLocal
from app.api import api_router
from app.api.ws.notifications import router as ws_notifications_router
from app.core.security import create_access_token, verify_password
from app.core.dependencies import get_db
from app.crud.user import user_crud
from app.schemas.token import Token
from app.schemas.user import UserCreate
from app.core.config import settings
from app.core.audit_middleware import AuditMiddleware
from app.services.document_reaper import reap_stuck_documents
from app.core.rate_limit import enforce_login_rate_limit

app = FastAPI(
    title="LegalOS Backend MVP",
    version="0.1.0",
    description="Backend API for Legal Document Operating System MVP",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Audit Middleware
app.add_middleware(AuditMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
    max_age=3600,
)


# Serve uploaded files (PDFs, etc.) from /uploads
uploads_path = Path(__file__).resolve().parent.parent / "uploads"
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads",
    StaticFiles(directory=str(uploads_path)),
    name="uploads",
)


@app.on_event("startup")
async def startup_event():
    # Create database tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("🚀 LegalOS Backend initialized.")

    async def _reaper_loop():
        # Run every 5 minutes
        while True:
            try:
                await reap_stuck_documents()
            except Exception:
                pass
            await asyncio.sleep(300)

    asyncio.create_task(_reaper_loop())


# Include all API routes
app.include_router(api_router)
app.include_router(ws_notifications_router, prefix="/api/v1/ws/notifications", tags=["websockets"])


@app.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Standard OAuth2 password login for token access."""
    # Very lightweight rate limiting: key by IP and username
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(f"{client_ip}:{form_data.username}")

    user = await user_crud.get_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # include identifying info so downstream dependencies can avoid extra
    # database lookups if desired (the payload is still verified on every
    # request by get_current_user).
    
    # Handle legacy users without a role set
    if user.role is None:
        user.role = UserRole.LAWYER
        db.add(user)
        await db.commit()
    
    token_data = {
        "email": user.email,
        "user_id": user.id,
        "org_id": user.organization_id,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/")
async def read_root():
    return {"message": "Welcome to LegalOS Backend MVP!", "version": "0.1.0", "docs": "/docs"}
