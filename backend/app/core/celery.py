import os
import logging
import time
from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun, task_retry

logger = logging.getLogger(__name__)
worker_logger = logging.getLogger("legalos.worker")
worker_logger.setLevel(logging.INFO)
if not worker_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    worker_logger.addHandler(handler)
worker_logger.propagate = False
_task_started_at: dict[str, float] = {}

REDIS_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "documents_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.document_tasks", "app.workers.workflow_tasks"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

logger.info(f"Celery configured with broker: {REDIS_URL}")

def safe_task_delay(task, *args, **kwargs):
    """Safely queue a Celery task with retry logic"""
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return task.delay(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Failed to queue task (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait 1 second before retry
            else:
                raise


def _extract_document_id(args, kwargs):
    if kwargs and "document_id" in kwargs:
        return kwargs.get("document_id")
    if args:
        first = args[0]
        if isinstance(first, int):
            return first
    return None


@task_prerun.connect
def log_task_start(sender=None, task_id=None, task=None, args=None, kwargs=None, **_extra):
    if task_id:
        _task_started_at[task_id] = time.perf_counter()
    worker_logger.info(
        "celery_task_start task_id=%s task=%s document_id=%s",
        task_id,
        getattr(sender, "name", None),
        _extract_document_id(args or (), kwargs or {}),
    )


@task_postrun.connect
def log_task_finish(sender=None, task_id=None, task=None, args=None, kwargs=None, state=None, retval=None, **_extra):
    started = _task_started_at.pop(task_id, None) if task_id else None
    duration_ms = int((time.perf_counter() - started) * 1000) if started else None
    worker_logger.info(
        "celery_task_finish task_id=%s task=%s state=%s duration_ms=%s document_id=%s",
        task_id,
        getattr(sender, "name", None),
        state,
        duration_ms,
        _extract_document_id(args or (), kwargs or {}),
    )


@task_failure.connect
def log_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, **_extra):
    worker_logger.warning(
        "celery_task_failure task_id=%s task=%s error_class=%s document_id=%s",
        task_id,
        getattr(sender, "name", None),
        type(exception).__name__ if exception else None,
        _extract_document_id(args or (), kwargs or {}),
    )


@task_retry.connect
def log_task_retry(sender=None, request=None, reason=None, **_extra):
    worker_logger.warning(
        "celery_task_retry task_id=%s task=%s reason=%s",
        getattr(request, "id", None),
        getattr(sender, "name", None),
        reason,
    )
