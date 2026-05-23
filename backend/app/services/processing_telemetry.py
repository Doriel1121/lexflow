"""Structured logging and DB persistence for document processing / AI stages."""
from __future__ import annotations

import logging
import time
import traceback
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document_processing_log import DocumentProcessingLog

logger = logging.getLogger("legalos.processing")


def get_ai_provider_name() -> str:
    try:
        from app.core.ai_provider import get_ai_provider

        provider = get_ai_provider()
        return type(provider).__name__
    except Exception:
        return "unknown"


def emit_stage(
    *,
    document_id: int,
    organization_id: Optional[int],
    stage: str,
    duration_ms: int,
    status: str = "ok",
    error_class: Optional[str] = None,
    provider: Optional[str] = None,
    **extra: Any,
) -> None:
    """Structured log line for aggregation (CloudWatch, Loki, etc.)."""
    payload = {
        "document_id": document_id,
        "organization_id": organization_id,
        "stage": stage,
        "duration_ms": duration_ms,
        "status": status,
        "provider": provider or get_ai_provider_name(),
    }
    if error_class:
        payload["error_class"] = error_class
    payload.update(extra)

    msg = (
        f"[processing] doc={document_id} org={organization_id} stage={stage} "
        f"status={status} duration_ms={duration_ms}"
    )
    if status == "error":
        logger.warning("%s %s", msg, payload)
    else:
        logger.info("%s %s", msg, payload)


@asynccontextmanager
async def track_stage(
    document_id: int,
    organization_id: Optional[int],
    stage: str,
    **extra: Any,
) -> AsyncIterator[None]:
    """Time a pipeline stage and emit structured logs."""
    started = time.perf_counter()
    err: Optional[BaseException] = None
    try:
        yield
    except BaseException as e:
        err = e
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit_stage(
            document_id=document_id,
            organization_id=organization_id,
            stage=stage,
            duration_ms=duration_ms,
            status="error" if err else "ok",
            error_class=type(err).__name__ if err else None,
            **extra,
        )


async def record_processing_error(
    db: AsyncSession,
    *,
    document_id: int,
    organization_id: Optional[int],
    stage: str,
    error: BaseException | str,
    stack_trace: Optional[str] = None,
    duration_ms: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Persist processing failure for org admin diagnostics."""
    message = str(error)
    if stack_trace is None and isinstance(error, BaseException):
        stack_trace = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    db.add(
        DocumentProcessingLog(
            document_id=document_id,
            organization_id=organization_id,
            stage=stage,
            event_type="error",
            error_message=message[:8000],
            stack_trace=stack_trace,
            duration_ms=duration_ms,
            metadata_json=metadata,
        )
    )
    await db.commit()

    emit_stage(
        document_id=document_id,
        organization_id=organization_id,
        stage=stage,
        duration_ms=duration_ms or 0,
        status="error",
        error_class=type(error).__name__ if isinstance(error, BaseException) else "Error",
    )
