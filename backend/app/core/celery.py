import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "documents_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.document_tasks"]
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
