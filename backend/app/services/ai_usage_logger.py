import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_usage_event import AIUsageEvent
from app.db.session import CeleryAsyncSessionLocal

logger = logging.getLogger(__name__)


def estimate_tokens(text_or_count: Any) -> Optional[int]:
    if text_or_count is None:
        return None
    if isinstance(text_or_count, int):
        chars = text_or_count
    elif isinstance(text_or_count, str):
        chars = len(text_or_count)
    else:
        chars = len(str(text_or_count))
    return max(1, round(chars / 4)) if chars > 0 else 0


def provider_name(provider: Any) -> str:
    return type(provider).__name__.replace("Provider", "").lower() or "unknown"


def provider_model(provider: Any) -> Optional[str]:
    model = getattr(provider, "model", None)
    if isinstance(model, str):
        return model
    model_name = getattr(model, "model_name", None) or getattr(model, "name", None)
    return str(model_name) if model_name else None


def safe_error_message(exc: BaseException, max_len: int = 500) -> str:
    return str(exc).replace("\n", " ")[:max_len]



async def record_ai_usage(
    db: Optional[AsyncSession],
    *,
    organization_id: Optional[int],
    task_type: str,
    provider: Any,
    status: str,
    latency_ms: Optional[int] = None,
    input_chars: Optional[int] = None,
    output_chars: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    if db is None:
        return
    try:
        async with CeleryAsyncSessionLocal() as telemetry_db:
            telemetry_db.add(
                AIUsageEvent(
                    organization_id=organization_id,
                    task_type=task_type,
                    provider=provider_name(provider),
                    model=provider_model(provider),
                    status=status,
                    latency_ms=latency_ms,
                    input_chars=input_chars,
                    output_chars=output_chars,
                    estimated_input_tokens=estimate_tokens(input_chars),
                    estimated_output_tokens=estimate_tokens(output_chars),
                    error_message=error_message,
                )
            )
            await telemetry_db.commit()
    except Exception as exc:
        logger.warning("Failed to record AI usage telemetry: %s", exc)


@asynccontextmanager
async def track_ai_call(
    db: Optional[AsyncSession],
    *,
    organization_id: Optional[int],
    task_type: str,
    provider: Any,
    input_text: Optional[str] = None,
    input_chars: Optional[int] = None,
) -> AsyncIterator[dict[str, Any]]:
    start = time.perf_counter()
    result_info: dict[str, Any] = {"output_chars": None}
    measured_input_chars = input_chars if input_chars is not None else (len(input_text) if input_text is not None else None)
    try:
        yield result_info
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        await record_ai_usage(
            db,
            organization_id=organization_id,
            task_type=task_type,
            provider=provider,
            status="error",
            latency_ms=latency_ms,
            input_chars=measured_input_chars,
            output_chars=result_info.get("output_chars"),
            error_message=safe_error_message(exc),
        )
        raise
    else:
        latency_ms = int((time.perf_counter() - start) * 1000)
        await record_ai_usage(
            db,
            organization_id=organization_id,
            task_type=task_type,
            provider=provider,
            status="success",
            latency_ms=latency_ms,
            input_chars=measured_input_chars,
            output_chars=result_info.get("output_chars"),
        )
