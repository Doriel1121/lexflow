from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.legal_workflow_constants import (
    LegalDraftStatus,
    WorkflowActorType,
    WorkflowStatus,
    WorkflowStepKey,
    WorkflowStepStatus,
    WorkflowStepType,
)
from app.crud.legal_workflow import legal_workflow_crud
from app.db.models.legal_workflow import LegalDraft, LegalWorkflow, LegalWorkflowStep
from app.schemas.legal_workflow import LegalDraftCreate, LegalWorkflowCreate, WorkflowEventCreate
from app.services.document_notifications import create_org_notification

logger = logging.getLogger(__name__)

# Import lazily to avoid circular dependencies at module load time
def _get_drafting_service():
    from app.services.legal_drafting import legal_drafting_service
    return legal_drafting_service


VALID_WORKFLOW_TRANSITIONS = {
    WorkflowStatus.CREATED.value: {WorkflowStatus.INTAKE_RECEIVED.value, WorkflowStatus.CANCELLED.value},
    WorkflowStatus.INTAKE_RECEIVED.value: {WorkflowStatus.INGESTING.value, WorkflowStatus.CANCELLED.value},
    WorkflowStatus.INGESTING.value: {
        WorkflowStatus.AI_ANALYZING.value,
        WorkflowStatus.INGESTION_FAILED.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.AI_ANALYZING.value: {WorkflowStatus.AI_DRAFTING.value, WorkflowStatus.CANCELLED.value},
    WorkflowStatus.AI_DRAFTING.value: {
        WorkflowStatus.PENDING_HUMAN_REVIEW.value,
        WorkflowStatus.AI_DRAFT_FAILED.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.AI_DRAFT_FAILED.value: {WorkflowStatus.AI_DRAFTING.value, WorkflowStatus.CANCELLED.value},
    WorkflowStatus.PENDING_HUMAN_REVIEW.value: {
        WorkflowStatus.IN_HUMAN_REVIEW.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.IN_HUMAN_REVIEW.value: {
        WorkflowStatus.REVISION_REQUESTED.value,
        WorkflowStatus.APPROVED_FOR_ASSEMBLY.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.REVISION_REQUESTED.value: {
        WorkflowStatus.AI_DRAFTING.value,
        WorkflowStatus.IN_HUMAN_REVIEW.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.APPROVED_FOR_ASSEMBLY.value: {
        WorkflowStatus.ASSEMBLING_BUNDLE.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.ASSEMBLING_BUNDLE.value: {
        WorkflowStatus.READY_FOR_COURT_SUBMISSION.value,
        WorkflowStatus.ASSEMBLY_FAILED.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.ASSEMBLY_FAILED.value: {
        WorkflowStatus.ASSEMBLING_BUNDLE.value,
        WorkflowStatus.CANCELLED.value,
    },
    WorkflowStatus.READY_FOR_COURT_SUBMISSION.value: {
        WorkflowStatus.SUBMITTED.value,
        WorkflowStatus.IN_HUMAN_REVIEW.value,
        WorkflowStatus.CANCELLED.value,
    },
}


class WorkflowEngine:
    async def create_workflow(
        self,
        db: AsyncSession,
        workflow_in: LegalWorkflowCreate,
        created_by_user_id: int,
        organization_id: int,
    ) -> LegalWorkflow:
        return await legal_workflow_crud.create_workflow(
            db,
            workflow_in,
            created_by_user_id=created_by_user_id,
            organization_id=organization_id,
        )

    async def start_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
        actor_user_id: Optional[int] = None,
    ) -> LegalWorkflow:
        workflow = await self._get_workflow_for_update(db, workflow_id, organization_id)
        if not workflow:
            raise ValueError("Workflow not found or not accessible")

        if workflow.status == WorkflowStatus.CANCELLED.value:
            raise ValueError("Cancelled workflows cannot be started")

        if workflow.status == WorkflowStatus.CREATED.value:
            workflow.started_at = datetime.utcnow()
            await self.transition_workflow(
                db,
                workflow,
                WorkflowStatus.INTAKE_RECEIVED.value,
                actor_user_id=actor_user_id,
                event_type="workflow.started",
            )
            await db.commit()
            await self.publish_workflow_update(db, workflow.id, organization_id, "Workflow started")

        return await legal_workflow_crud.get_workflow(db, workflow_id, organization_id) or workflow

    async def advance_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
    ) -> LegalWorkflow:
        workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
        if not workflow:
            raise ValueError("Workflow not found or not accessible")

        while workflow.status not in {
            WorkflowStatus.PENDING_HUMAN_REVIEW.value,
            WorkflowStatus.IN_HUMAN_REVIEW.value,
            WorkflowStatus.APPROVED_FOR_ASSEMBLY.value,
            WorkflowStatus.CANCELLED.value,
            WorkflowStatus.READY_FOR_COURT_SUBMISSION.value,
        }:
            step = await self.claim_next_step(db, workflow_id, organization_id)
            if not step:
                break

            workflow = await self._get_workflow_for_update(db, workflow_id, organization_id)
            if not workflow:
                raise ValueError("Workflow not found or not accessible")

            await self.start_step(db, step, workflow=workflow)

            if step.step_type == WorkflowStepType.HUMAN.value:
                step.status = WorkflowStepStatus.WAITING_FOR_HUMAN.value
                await self._set_human_waiting_status(db, workflow, step)
                await db.commit()
                await self.publish_workflow_update(db, workflow.id, organization_id, "Waiting for human review")
                break

            await self._run_mock_automated_step(db, workflow, step)
            await self.complete_step(db, step, workflow=workflow)
            await db.commit()
            await self.publish_workflow_update(db, workflow.id, organization_id, f"Completed {step.step_key}")
            workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id) or workflow

        return await legal_workflow_crud.get_workflow(db, workflow_id, organization_id) or workflow

    async def claim_next_step(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
    ) -> Optional[LegalWorkflowStep]:
        await legal_workflow_crud._ensure_workflow_access(db, workflow_id, organization_id)
        result = await db.execute(
            select(LegalWorkflowStep)
            .where(
                LegalWorkflowStep.workflow_id == workflow_id,
                LegalWorkflowStep.status.in_([WorkflowStepStatus.PENDING.value, WorkflowStepStatus.QUEUED.value]),
            )
            .order_by(LegalWorkflowStep.ordinal)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        step = result.scalars().first()
        if not step:
            return None
        step.status = WorkflowStepStatus.QUEUED.value
        step.attempt_count = (step.attempt_count or 0) + 1
        await db.flush()
        return step

    async def start_step(
        self,
        db: AsyncSession,
        step: LegalWorkflowStep,
        workflow: LegalWorkflow,
        celery_task_id: Optional[str] = None,
    ) -> LegalWorkflowStep:
        step.status = WorkflowStepStatus.RUNNING.value
        step.started_at = datetime.utcnow()
        step.celery_task_id = celery_task_id
        workflow.current_step_key = step.step_key
        await legal_workflow_crud.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type="step.started",
                actor_type=WorkflowActorType.WORKER,
                step_key=step.step_key,
                payload={"attempt_count": step.attempt_count},
            ),
            commit=False,
        )
        await self._transition_for_step_start(db, workflow, step)
        await db.flush()
        return step

    async def complete_step(
        self,
        db: AsyncSession,
        step: LegalWorkflowStep,
        workflow: LegalWorkflow,
        output_artifact_ids: Optional[list[int]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> LegalWorkflowStep:
        step.status = WorkflowStepStatus.COMPLETED.value
        step.progress = 100
        step.completed_at = datetime.utcnow()
        if output_artifact_ids is not None:
            step.output_artifact_ids = output_artifact_ids
        await legal_workflow_crud.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type="step.completed",
                actor_type=WorkflowActorType.WORKER,
                step_key=step.step_key,
                payload=payload or {},
            ),
            commit=False,
        )
        await self._transition_for_step_completion(db, workflow, step)
        await db.flush()
        return step

    async def fail_step(
        self,
        db: AsyncSession,
        step: LegalWorkflowStep,
        workflow: LegalWorkflow,
        error: dict[str, Any],
    ) -> LegalWorkflowStep:
        step.status = WorkflowStepStatus.FAILED.value
        step.error = error
        step.completed_at = datetime.utcnow()
        workflow.error = error
        if step.step_key.startswith("draft."):
            workflow.status = WorkflowStatus.AI_DRAFT_FAILED.value
        elif step.step_key.startswith("bundle."):
            workflow.status = WorkflowStatus.ASSEMBLY_FAILED.value
        await legal_workflow_crud.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type="step.failed",
                actor_type=WorkflowActorType.WORKER,
                step_key=step.step_key,
                payload={"error": error},
            ),
            commit=False,
        )
        await db.commit()
        await self.publish_workflow_update(db, workflow.id, workflow.organization_id, "Workflow step failed")
        return step

    async def transition_workflow(
        self,
        db: AsyncSession,
        workflow: LegalWorkflow,
        to_status: str,
        actor_user_id: Optional[int] = None,
        event_type: str = "workflow.transitioned",
        payload: Optional[dict[str, Any]] = None,
    ) -> LegalWorkflow:
        from_status = workflow.status
        if from_status != to_status and to_status not in VALID_WORKFLOW_TRANSITIONS.get(from_status, set()):
            raise ValueError(f"Invalid workflow transition: {from_status} -> {to_status}")

        workflow.status = to_status
        if to_status in {
            WorkflowStatus.READY_FOR_COURT_SUBMISSION.value,
            WorkflowStatus.SUBMITTED.value,
            WorkflowStatus.CANCELLED.value,
        }:
            workflow.completed_at = datetime.utcnow()

        await legal_workflow_crud.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type=event_type,
                actor_type=WorkflowActorType.USER if actor_user_id else WorkflowActorType.SYSTEM,
                actor_user_id=actor_user_id,
                payload={"from_status": from_status, "to_status": to_status, **(payload or {})},
            ),
            commit=False,
        )
        await db.flush()
        return workflow

    async def cancel_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
        actor_user_id: int,
    ) -> LegalWorkflow:
        workflow = await self._get_workflow_for_update(db, workflow_id, organization_id)
        if not workflow:
            raise ValueError("Workflow not found or not accessible")
        await self.transition_workflow(
            db,
            workflow,
            WorkflowStatus.CANCELLED.value,
            actor_user_id=actor_user_id,
            event_type="workflow.cancelled",
        )
        await db.commit()
        await self.publish_workflow_update(db, workflow.id, organization_id, "Workflow cancelled")
        return await legal_workflow_crud.get_workflow(db, workflow_id, organization_id) or workflow

    async def retry_step(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
        step_key: str,
        actor_user_id: int,
    ) -> LegalWorkflowStep:
        workflow = await self._get_workflow_for_update(db, workflow_id, organization_id)
        if not workflow:
            raise ValueError("Workflow not found or not accessible")

        result = await db.execute(
            select(LegalWorkflowStep).where(
                LegalWorkflowStep.workflow_id == workflow_id,
                LegalWorkflowStep.step_key == step_key,
            )
        )
        step = result.scalars().first()
        if not step:
            raise ValueError("Step not found")
        if step.status != WorkflowStepStatus.FAILED.value:
            raise ValueError("Only failed steps can be retried")

        step.status = WorkflowStepStatus.PENDING.value
        step.error = None
        step.completed_at = None
        workflow.error = None
        if step_key.startswith("draft."):
            workflow.status = WorkflowStatus.AI_DRAFTING.value
        elif step_key.startswith("bundle."):
            workflow.status = WorkflowStatus.ASSEMBLING_BUNDLE.value
        await legal_workflow_crud.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type="step.retry_requested",
                actor_type=WorkflowActorType.USER,
                actor_user_id=actor_user_id,
                step_key=step.step_key,
                payload={"attempt_count": step.attempt_count},
            ),
            commit=False,
        )
        await db.commit()
        return step

    async def publish_workflow_update(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
        message: str,
    ) -> None:
        workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
        if not workflow:
            return
        try:
            await create_org_notification(
                db,
                organization_id=organization_id,
                event_type="WORKFLOW_STATUS_UPDATE",
                title="Workflow Updated",
                message=message,
                source_type="workflow",
                source_id=workflow_id,
                extra_payload={
                    "workflow_id": workflow.id,
                    "case_id": workflow.case_id,
                    "status": workflow.status,
                    "current_step_key": workflow.current_step_key,
                },
            )
        except Exception:
            logger.warning("Failed to publish workflow update for workflow %s", workflow_id, exc_info=True)

    async def _transition_for_step_start(
        self,
        db: AsyncSession,
        workflow: LegalWorkflow,
        step: LegalWorkflowStep,
    ) -> None:
        target = None
        if step.step_key == WorkflowStepKey.INTAKE_CAPTURE.value:
            target = WorkflowStatus.INTAKE_RECEIVED.value
        elif step.step_key in {WorkflowStepKey.INTAKE_PERSIST_SOURCE_DOCUMENT.value, WorkflowStepKey.DOCUMENT_OCR.value}:
            target = WorkflowStatus.INGESTING.value
        elif step.step_key == WorkflowStepKey.DOCUMENT_AI_ANALYSIS.value:
            target = WorkflowStatus.AI_ANALYZING.value
        elif step.step_key.startswith("draft."):
            target = WorkflowStatus.AI_DRAFTING.value
        elif step.step_key.startswith("bundle."):
            target = WorkflowStatus.ASSEMBLING_BUNDLE.value

        if target and workflow.status != target:
            await self.transition_workflow(db, workflow, target, event_type="workflow.transitioned")

    async def _transition_for_step_completion(
        self,
        db: AsyncSession,
        workflow: LegalWorkflow,
        step: LegalWorkflowStep,
    ) -> None:
        if step.step_key == WorkflowStepKey.DRAFT_NORMALIZE_TO_EDITOR_DOC.value:
            await self.transition_workflow(db, workflow, WorkflowStatus.PENDING_HUMAN_REVIEW.value)
        elif step.step_key == WorkflowStepKey.BUNDLE_FINALIZE.value:
            await self.transition_workflow(db, workflow, WorkflowStatus.READY_FOR_COURT_SUBMISSION.value)

    async def _set_human_waiting_status(
        self,
        db: AsyncSession,
        workflow: LegalWorkflow,
        step: LegalWorkflowStep,
    ) -> None:
        if step.step_key == WorkflowStepKey.REVIEW_HUMAN_EDIT.value:
            target = WorkflowStatus.IN_HUMAN_REVIEW.value
        else:
            target = workflow.status
        if target != workflow.status:
            await self.transition_workflow(db, workflow, target, event_type="workflow.waiting_for_human")
        await legal_workflow_crud.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type="step.waiting_for_human",
                actor_type=WorkflowActorType.SYSTEM,
                step_key=step.step_key,
            ),
            commit=False,
        )

    async def _run_mock_automated_step(
        self,
        db: AsyncSession,
        workflow: LegalWorkflow,
        step: LegalWorkflowStep,
    ) -> None:
        if step.step_key == WorkflowStepKey.DRAFT_GENERATE.value:
            # Use the real AI drafting service (idempotent – skips if draft exists)
            try:
                drafting_service = _get_drafting_service()
                await drafting_service.generate_draft(db, workflow)
            except Exception as exc:
                logger.error(
                    "Draft generation failed for workflow %s: %s",
                    workflow.id,
                    exc,
                    exc_info=True,
                )
                raise

    async def _get_existing_draft(self, db: AsyncSession, workflow_id: int) -> Optional[LegalDraft]:
        result = await db.execute(
            select(LegalDraft)
            .where(LegalDraft.workflow_id == workflow_id)
            .order_by(LegalDraft.version.desc(), LegalDraft.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def _get_workflow_for_update(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
    ) -> Optional[LegalWorkflow]:
        result = await db.execute(
            select(LegalWorkflow)
            .options(selectinload(LegalWorkflow.steps))
            .where(LegalWorkflow.id == workflow_id, LegalWorkflow.organization_id == organization_id)
            .with_for_update()
        )
        return result.scalars().first()


workflow_engine = WorkflowEngine()
