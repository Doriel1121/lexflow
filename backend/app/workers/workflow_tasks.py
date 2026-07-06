import asyncio
import logging

from celery import shared_task

from app.core.config import settings
from app.db.session import CeleryAsyncSessionLocal
from app.services.workflow_engine import workflow_engine

logger = logging.getLogger(__name__)


def run_async(coro):
    return asyncio.run(coro)


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def start_workflow_task(self, workflow_id: int, organization_id: int):
    if not settings.LEGAL_WORKFLOWS_ENABLED:
        logger.info("Skipping workflow %s start task; legal workflows are disabled.", workflow_id)
        return

    async def _run():
        async with CeleryAsyncSessionLocal() as db:
            await workflow_engine.start_workflow(db, workflow_id, organization_id)
            await workflow_engine.advance_workflow(db, workflow_id, organization_id)

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("Workflow %s start task failed: %s", workflow_id, exc, exc_info=True)
        raise


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def run_ai_drafting_step(self, workflow_id: int, organization_id: int):
    if not settings.LEGAL_WORKFLOWS_ENABLED:
        logger.info("Skipping workflow %s drafting task; legal workflows are disabled.", workflow_id)
        return

    async def _run():
        async with CeleryAsyncSessionLocal() as db:
            await workflow_engine.advance_workflow(db, workflow_id, organization_id)

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("Workflow %s drafting task failed: %s", workflow_id, exc, exc_info=True)
        raise


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def run_bundle_assembly_step(self, workflow_id: int, organization_id: int):
    if not settings.LEGAL_WORKFLOWS_ENABLED:
        logger.info("Skipping workflow %s bundle task; legal workflows are disabled.", workflow_id)
        return

    async def _run():
        async with CeleryAsyncSessionLocal() as db:
            from app.services.court_bundle_assembler import court_bundle_assembler
            await court_bundle_assembler.assemble_bundle(db, workflow_id, organization_id)

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("Workflow %s bundle task failed: %s", workflow_id, exc, exc_info=True)
        raise


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def retry_workflow_step(self, workflow_id: int, organization_id: int, step_key: str, actor_user_id: int):
    if not settings.LEGAL_WORKFLOWS_ENABLED:
        logger.info(
            "Skipping workflow %s retry task for %s; legal workflows are disabled.",
            workflow_id,
            step_key,
        )
        return

    async def _run():
        async with CeleryAsyncSessionLocal() as db:
            await workflow_engine.retry_step(db, workflow_id, organization_id, step_key, actor_user_id)
            await workflow_engine.advance_workflow(db, workflow_id, organization_id)

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("Workflow %s retry task failed for %s: %s", workflow_id, step_key, exc, exc_info=True)
        raise
