from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import timedelta
import asyncio
import logging
import time
import uuid
from pathlib import Path

from app.db.session import engine, Base, AsyncSessionLocal
from sqlalchemy import text
from app.api import api_router
from app.api.ws.notifications import router as ws_notifications_router
from app.core.security import create_access_token, verify_password
from app.core.dependencies import get_db
from app.crud.user import user_crud
from app.schemas.token import Token
from app.schemas.user import UserCreate
from app.core.config import settings
from app.core.audit_middleware import AuditMiddleware
from app.core.rbac_middleware import RBACMiddleware
from app.services.document_reaper import reap_stuck_documents
from app.services.system_analytics import run_daily_aggregation
from app.core.rate_limit import enforce_login_rate_limit
from app.db.models.user import UserRole

request_logger = logging.getLogger("legalos.api")
request_logger.setLevel(logging.INFO)
if not request_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    request_logger.addHandler(handler)
request_logger.propagate = False

app = FastAPI(
    title="LegalOS Backend MVP",
    version="0.1.0",
    description="Backend API for Legal Document Operating System MVP",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500

    try:
        timeout_seconds = settings.API_REQUEST_TIMEOUT_SECONDS
        if timeout_seconds and timeout_seconds > 0:
            response = await asyncio.wait_for(call_next(request), timeout=timeout_seconds)
        else:
            response = await call_next(request)
        status_code = response.status_code
        return response
    except asyncio.TimeoutError:
        status_code = 504
        duration_ms = int((time.perf_counter() - started) * 1000)
        request_logger.warning(
            "api_request_timeout request_id=%s method=%s path=%s status=%s duration_ms=%s timeout_seconds=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            settings.API_REQUEST_TIMEOUT_SECONDS,
        )
        response = JSONResponse(status_code=504, content={"detail": "Request timed out"})
        return response
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        request_logger.exception(
            "api_request_error request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        response_obj = locals().get("response")
        if response_obj is not None:
            response_obj.headers["X-Request-ID"] = request_id
            response_obj.headers["X-Response-Time-ms"] = str(duration_ms)

        log_level = logging.WARNING if status_code >= 500 else logging.INFO
        request_logger.log(
            log_level,
            "api_request request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )

# ── Middleware stack (order matters: outer runs first on request) ──────────
#
#  Request  →  CORSMiddleware  →  AuditMiddleware  →  RBACMiddleware  →  Route
#  Response ←  CORSMiddleware  ←  AuditMiddleware  ←  RBACMiddleware  ←  Route
#
# RBACMiddleware must run AFTER AuditMiddleware sets request.state.user.
# In Starlette, add_middleware() wraps in reverse order, so we add
# RBACMiddleware first (innermost) then AuditMiddleware (outermost of the two).

app.add_middleware(RBACMiddleware)   # innermost: runs after auth sets state.user
app.add_middleware(AuditMiddleware)  # outermost: sets state.user, then logs

def _get_frontend_origins() -> list[str]:
    raw = settings.FRONTEND_ORIGINS or ""
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if settings.ENVIRONMENT == "development":
        # Always allow local dev origins in development
        for origin in ["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"]:
            if origin not in origins:
                origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_frontend_origins(),
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
    # Create tables if they don't exist (fallback for migration issues)
    # This is a development safeguard - production should use alembic migrations
    try:
        # Get all table names from metadata
        table_names = list(Base.metadata.tables.keys())
        
        # Use a direct connection and create tables synchronously
        # This is more reliable than async run_sync() for table creation
        import sqlalchemy as sa
        from sqlalchemy import create_engine, text
        
        # Create a synchronous engine for table creation only
        # Replace async driver with sync psycopg2
        sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        sync_engine = create_engine(sync_db_url, echo=False, isolation_level="AUTOCOMMIT")
        
        # Check if tables already exist and create if needed
        with sync_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) as cnt FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            existing_table_count = result.scalar()
            if existing_table_count is None:
                existing_table_count = 0
            
            if existing_table_count == 0:
                # Database is empty, create all tables
                Base.metadata.create_all(sync_engine)
            
        sync_engine.dispose()
        
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"ERROR creating tables: {type(e).__name__}: {e}")
        traceback.print_exc()
    
    print("🚀 LegalOS Backend initialized.")

    async def _reaper_loop():
        while True:
            try:
                await reap_stuck_documents()
            except Exception:
                pass
            await asyncio.sleep(300)

    async def _analytics_aggregation_loop():
        while True:
            try:
                await run_daily_aggregation()
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Analytics aggregation error: %s", exc)
            await asyncio.sleep(900)  # 15 minutes

    asyncio.create_task(_reaper_loop())
    asyncio.create_task(_analytics_aggregation_loop())


app.include_router(api_router)
app.include_router(ws_notifications_router, prefix="/api/v1/ws/notifications", tags=["websockets"])
app.include_router(ws_notifications_router, prefix="/v1/ws/notifications", tags=["websockets"])


@app.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
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
    access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/")
async def read_root():
    return {"message": "Welcome to LegalOS Backend MVP!", "version": "0.1.0", "docs": "/docs"}


@app.get("/metrics-lite")
async def metrics_lite():
    async def check_db():
        started = time.perf_counter()
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return {"ok": True, "latency_ms": int((time.perf_counter() - started) * 1000)}
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": type(exc).__name__,
            }

    async def check_redis():
        started = time.perf_counter()
        try:
            import redis.asyncio as redis

            client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            try:
                await client.ping()
            finally:
                await client.aclose()
            return {"ok": True, "latency_ms": int((time.perf_counter() - started) * 1000)}
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": type(exc).__name__,
            }

    async def check_queue_depths():
        started = time.perf_counter()
        try:
            import redis.asyncio as redis

            client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            try:
                queues = [
                    queue.strip()
                    for queue in settings.METRICS_CELERY_QUEUES.split(",")
                    if queue.strip()
                ]
                depths = {queue: await client.llen(queue) for queue in queues}
            finally:
                await client.aclose()
            return {
                "ok": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "queues": depths,
                "total_depth": sum(depths.values()),
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": type(exc).__name__,
                "queues": {},
                "total_depth": None,
            }

    async def check_celery():
        started = time.perf_counter()
        try:
            from app.core.celery import celery_app

            ping = await asyncio.wait_for(
                asyncio.to_thread(lambda: celery_app.control.inspect(timeout=1).ping()),
                timeout=2,
            )
            workers = sorted((ping or {}).keys())
            return {
                "ok": bool(workers),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "workers": workers,
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": type(exc).__name__,
                "workers": [],
            }

    db_status, redis_status, celery_status, queue_status = await asyncio.gather(
        check_db(),
        check_redis(),
        check_celery(),
        check_queue_depths(),
    )
    overall_ok = db_status["ok"] and redis_status["ok"]
    status_code = 200 if overall_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": overall_ok,
            "services": {
                "db": db_status,
                "redis": redis_status,
                "celery": celery_status,
                "queues": queue_status,
            },
        },
    )
