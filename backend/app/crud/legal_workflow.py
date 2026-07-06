from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.legal_workflow_constants import (
    DEFAULT_COURT_RESPONSE_WORKFLOW_STEPS,
    CourtBundleStatus,
    LegalDraftStatus,
    WorkflowActorType,
    WorkflowStepStatus,
    WorkflowStatus,
)
from app.db.models.case import Case as DBCase
from app.db.models.document import Document as DBDocument
from app.db.models.legal_workflow import (
    CourtBundle as DBCourtBundle,
    LegalArtifact as DBLegalArtifact,
    LegalDraft as DBLegalDraft,
    LegalWorkflow as DBLegalWorkflow,
    LegalWorkflowStep as DBLegalWorkflowStep,
    WorkflowEvent as DBWorkflowEvent,
)
from app.schemas.legal_workflow import (
    CourtBundleCreate,
    LegalArtifactCreate,
    LegalDraftCreate,
    LegalDraftUpdate,
    LegalWorkflowCreate,
    WorkflowEventCreate,
)


class CRUDLegalWorkflow:
    async def create_workflow(
        self,
        db: AsyncSession,
        workflow_in: LegalWorkflowCreate,
        created_by_user_id: int,
        organization_id: int,
    ) -> DBLegalWorkflow:
        await self._ensure_case_access(db, workflow_in.case_id, organization_id)
        if workflow_in.source_document_id:
            await self._ensure_document_access(db, workflow_in.source_document_id, workflow_in.case_id, organization_id)

        workflow = DBLegalWorkflow(
            organization_id=organization_id,
            case_id=workflow_in.case_id,
            workflow_type=workflow_in.workflow_type.value,
            status=WorkflowStatus.CREATED.value,
            current_step_key=None,
            source_document_id=workflow_in.source_document_id,
            assigned_user_id=workflow_in.assigned_user_id,
            created_by_user_id=created_by_user_id,
            metadata_json=workflow_in.metadata,
        )
        db.add(workflow)
        await db.flush()
        await self.create_default_steps(db, workflow)
        await self.create_event(
            db,
            workflow,
            WorkflowEventCreate(
                event_type="workflow.created",
                actor_type=WorkflowActorType.USER,
                actor_user_id=created_by_user_id,
                payload={"workflow_type": workflow.workflow_type},
            ),
            commit=False,
        )
        await db.commit()
        return await self.get_workflow(db, workflow.id, organization_id) or workflow

    async def get_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
    ) -> Optional[DBLegalWorkflow]:
        result = await db.execute(
            select(DBLegalWorkflow)
            .options(
                selectinload(DBLegalWorkflow.steps),
                selectinload(DBLegalWorkflow.drafts),
                selectinload(DBLegalWorkflow.bundles),
                selectinload(DBLegalWorkflow.events),
            )
            .filter(
                DBLegalWorkflow.id == workflow_id,
                DBLegalWorkflow.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_case_workflows(
        self,
        db: AsyncSession,
        case_id: int,
        organization_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[DBLegalWorkflow]:
        await self._ensure_case_access(db, case_id, organization_id)
        result = await db.execute(
            select(DBLegalWorkflow)
            .options(
                selectinload(DBLegalWorkflow.steps),
                selectinload(DBLegalWorkflow.bundles),
                selectinload(DBLegalWorkflow.drafts),
                selectinload(DBLegalWorkflow.events),
            )
            .filter(
                DBLegalWorkflow.case_id == case_id,
                DBLegalWorkflow.organization_id == organization_id,
            )
            .order_by(DBLegalWorkflow.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_default_steps(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
    ) -> List[DBLegalWorkflowStep]:
        steps = [
            DBLegalWorkflowStep(
                workflow_id=workflow.id,
                step_key=step_key,
                step_type=step_type,
                status=WorkflowStepStatus.PENDING.value,
                ordinal=ordinal,
                depends_on=[] if ordinal == 0 else [DEFAULT_COURT_RESPONSE_WORKFLOW_STEPS[ordinal - 1][0]],
            )
            for ordinal, (step_key, step_type) in enumerate(DEFAULT_COURT_RESPONSE_WORKFLOW_STEPS)
        ]
        db.add_all(steps)
        await db.flush()
        return steps

    async def get_steps(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
    ) -> List[DBLegalWorkflowStep]:
        await self._ensure_workflow_access(db, workflow_id, organization_id)
        result = await db.execute(
            select(DBLegalWorkflowStep)
            .filter(DBLegalWorkflowStep.workflow_id == workflow_id)
            .order_by(DBLegalWorkflowStep.ordinal)
        )
        return list(result.scalars().all())

    async def create_event(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
        event_in: WorkflowEventCreate,
        commit: bool = True,
    ) -> DBWorkflowEvent:
        event = DBWorkflowEvent(
            organization_id=workflow.organization_id,
            case_id=workflow.case_id,
            workflow_id=workflow.id,
            step_key=event_in.step_key,
            event_type=event_in.event_type,
            actor_type=event_in.actor_type.value if hasattr(event_in.actor_type, "value") else event_in.actor_type,
            actor_user_id=event_in.actor_user_id,
            payload=event_in.payload,
        )
        db.add(event)
        if commit:
            await db.commit()
            await db.refresh(event)
        else:
            await db.flush()
        return event

    async def create_artifact(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
        artifact_in: LegalArtifactCreate,
        created_by_user_id: Optional[int] = None,
    ) -> DBLegalArtifact:
        artifact = DBLegalArtifact(
            organization_id=workflow.organization_id,
            case_id=workflow.case_id,
            workflow_id=workflow.id,
            artifact_type=artifact_in.artifact_type,
            document_id=artifact_in.document_id,
            storage_url=artifact_in.storage_url,
            storage_key=artifact_in.storage_key,
            mime_type=artifact_in.mime_type,
            filename=artifact_in.filename,
            checksum=artifact_in.checksum,
            size_bytes=artifact_in.size_bytes,
            metadata_json=artifact_in.metadata,
            created_by_user_id=created_by_user_id,
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        return artifact

    async def create_draft(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
        draft_in: LegalDraftCreate,
        created_by_user_id: Optional[int] = None,
    ) -> DBLegalDraft:
        draft = DBLegalDraft(
            organization_id=workflow.organization_id,
            case_id=workflow.case_id,
            workflow_id=workflow.id,
            source_document_id=draft_in.source_document_id or workflow.source_document_id,
            status=draft_in.status.value if hasattr(draft_in.status, "value") else draft_in.status,
            title=draft_in.title,
            editor_format=draft_in.editor_format,
            content_json=draft_in.content_json,
            content_text=draft_in.content_text,
            html_snapshot=draft_in.html_snapshot,
            created_by=draft_in.created_by,
            created_by_user_id=created_by_user_id,
        )
        db.add(draft)
        await db.flush()
        workflow.active_draft_id = draft.id
        await db.commit()
        await db.refresh(draft)
        return draft

    async def update_draft(
        self,
        db: AsyncSession,
        draft_id: int,
        organization_id: int,
        draft_in: LegalDraftUpdate,
    ) -> Optional[DBLegalDraft]:
        draft = await self._get_draft(db, draft_id, organization_id)
        if not draft:
            return None

        update_data = draft_in.model_dump(exclude_unset=True)
        if "status" in update_data and hasattr(update_data["status"], "value"):
            update_data["status"] = update_data["status"].value
        for field, value in update_data.items():
            setattr(draft, field, value)

        await db.commit()
        await db.refresh(draft)
        return draft

    async def approve_draft(
        self,
        db: AsyncSession,
        draft_id: int,
        organization_id: int,
        approved_by_user_id: int,
    ) -> Optional[DBLegalDraft]:
        draft = await self._get_draft(db, draft_id, organization_id, load_workflow=True)
        if not draft:
            return None

        draft.status = LegalDraftStatus.APPROVED.value
        draft.approved_by_user_id = approved_by_user_id
        draft.approved_at = datetime.utcnow()
        draft.workflow.status = WorkflowStatus.APPROVED_FOR_ASSEMBLY.value
        draft.workflow.active_draft_id = draft.id

        # Mark human review steps as completed
        for step in draft.workflow.steps:
            if step.step_key in ("review.human_edit", "review.approve"):
                step.status = WorkflowStepStatus.COMPLETED.value
                step.completed_at = datetime.utcnow()

        await self.create_event(
            db,
            draft.workflow,
            WorkflowEventCreate(
                event_type="draft.approved",
                actor_type=WorkflowActorType.USER,
                actor_user_id=approved_by_user_id,
                payload={"draft_id": draft.id},
            ),
            commit=False,
        )
        await db.commit()
        await db.refresh(draft)
        return draft

    async def create_bundle(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
        bundle_in: CourtBundleCreate,
    ) -> DBCourtBundle:
        bundle = DBCourtBundle(
            organization_id=workflow.organization_id,
            case_id=workflow.case_id,
            workflow_id=workflow.id,
            status=CourtBundleStatus.PENDING.value,
            approved_draft_id=bundle_in.approved_draft_id,
            jurisdiction=bundle_in.jurisdiction,
            court_profile=bundle_in.court_profile,
            max_chunk_bytes=bundle_in.max_chunk_bytes,
        )
        db.add(bundle)
        await db.flush()
        workflow.final_bundle_id = bundle.id
        await db.commit()
        await db.refresh(bundle)
        return bundle

    async def _ensure_case_access(self, db: AsyncSession, case_id: int, organization_id: int) -> DBCase:
        result = await db.execute(
            select(DBCase).filter(DBCase.id == case_id, DBCase.organization_id == organization_id)
        )
        case = result.scalars().first()
        if not case:
            raise ValueError("Case not found or not accessible")
        return case

    async def _ensure_document_access(
        self,
        db: AsyncSession,
        document_id: int,
        case_id: int,
        organization_id: int,
    ) -> DBDocument:
        result = await db.execute(
            select(DBDocument).filter(
                DBDocument.id == document_id,
                DBDocument.case_id == case_id,
                DBDocument.organization_id == organization_id,
            )
        )
        document = result.scalars().first()
        if not document:
            raise ValueError("Document not found or not accessible")
        return document

    async def _ensure_workflow_access(
        self,
        db: AsyncSession,
        workflow_id: int,
        organization_id: int,
    ) -> DBLegalWorkflow:
        workflow = await self.get_workflow(db, workflow_id, organization_id)
        if not workflow:
            raise ValueError("Workflow not found or not accessible")
        return workflow

    async def _get_draft(
        self,
        db: AsyncSession,
        draft_id: int,
        organization_id: int,
        load_workflow: bool = False,
    ) -> Optional[DBLegalDraft]:
        query = select(DBLegalDraft).filter(
            DBLegalDraft.id == draft_id,
            DBLegalDraft.organization_id == organization_id,
        )
        if load_workflow:
            query = query.options(
                selectinload(DBLegalDraft.workflow).selectinload(DBLegalWorkflow.steps)
            )
        result = await db.execute(query)
        return result.scalars().first()


legal_workflow_crud = CRUDLegalWorkflow()
