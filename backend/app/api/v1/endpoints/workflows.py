from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery import safe_task_delay
from app.core.dependencies import RoleChecker, get_current_org, get_db
from app.core.legal_workflow_constants import (
    CourtBundleStatus,
    LegalDraftStatus,
    WorkflowActorType,
    WorkflowStatus as WFStatus,
)
from app.crud.legal_workflow import legal_workflow_crud
from app.db.models.legal_workflow import (
    CourtBundle as DBCourtBundle,
    CourtBundleItem as DBCourtBundleItem,
    LegalArtifact as DBLegalArtifact,
    LegalDraft as DBLegalDraft,
    WorkflowEvent as DBWorkflowEvent,
)
from app.db.models.user import User as DBUser, UserRole
from app.schemas.legal_workflow import (
    CourtBundleCreate,
    CourtBundleSummary,
    LegalDraft,
    LegalDraftCreate,
    LegalDraftUpdate,
    LegalWorkflowCreate,
    LegalWorkflowDetail,
    WorkflowEvent,
    WorkflowEventCreate,
)
from app.services.workflow_engine import workflow_engine
from app.workers.workflow_tasks import run_ai_drafting_step, run_bundle_assembly_step, start_workflow_task

router = APIRouter()


class DraftRevisionRequest(BaseModel):
    instructions: Optional[str] = None


def _require_org(org_id: int | None) -> int:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context is required")
    return org_id


def _workflow_detail(workflow) -> Dict[str, Any]:
    events = sorted(workflow.events or [], key=lambda event: event.created_at or 0, reverse=True)[:25]
    bundle = None
    if workflow.final_bundle_id and workflow.bundles:
        bundle = next((item for item in workflow.bundles if item.id == workflow.final_bundle_id), None)
    if bundle is None and workflow.bundles:
        bundle = sorted(workflow.bundles, key=lambda item: item.created_at or 0, reverse=True)[0]

    return {
        "id": workflow.id,
        "organization_id": workflow.organization_id,
        "case_id": workflow.case_id,
        "workflow_type": workflow.workflow_type,
        "status": workflow.status,
        "current_step_key": workflow.current_step_key,
        "source_document_id": workflow.source_document_id,
        "active_draft_id": workflow.active_draft_id,
        "final_bundle_id": workflow.final_bundle_id,
        "assigned_user_id": workflow.assigned_user_id,
        "created_by_user_id": workflow.created_by_user_id,
        "metadata": workflow.metadata_json or {},
        "error": workflow.error,
        "started_at": workflow.started_at,
        "completed_at": workflow.completed_at,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
        "steps": sorted(workflow.steps or [], key=lambda step: step.ordinal),
        "drafts": sorted(workflow.drafts or [], key=lambda draft: draft.created_at or 0, reverse=True),
        "bundle": bundle,
        "recent_events": events,
    }


# =============================================================================
# Workflow CRUD Endpoints
# =============================================================================

@router.post("/workflows", response_model=LegalWorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_in: LegalWorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int | None = Depends(get_current_org),
):
    try:
        workflow = await workflow_engine.create_workflow(
            db,
            workflow_in,
            created_by_user_id=current_user.id,
            organization_id=_require_org(org_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _workflow_detail(workflow)


@router.get("/workflows/{workflow_id}", response_model=LegalWorkflowDetail)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
):
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, _require_org(org_id))
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return _workflow_detail(workflow)


@router.get("/cases/{case_id}/workflows", response_model=List[LegalWorkflowDetail])
async def list_case_workflows(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
    skip: int = 0,
    limit: int = 100,
):
    try:
        workflows = await legal_workflow_crud.list_case_workflows(db, case_id, _require_org(org_id), skip=skip, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [_workflow_detail(workflow) for workflow in workflows]


@router.post("/workflows/{workflow_id}/start", response_model=LegalWorkflowDetail)
async def start_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int | None = Depends(get_current_org),
):
    organization_id = _require_org(org_id)
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    safe_task_delay(start_workflow_task, workflow_id=workflow_id, organization_id=organization_id)
    await workflow_engine.start_workflow(db, workflow_id, organization_id, actor_user_id=current_user.id)
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
    return _workflow_detail(workflow)


@router.post("/workflows/{workflow_id}/cancel", response_model=LegalWorkflowDetail)
async def cancel_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int | None = Depends(get_current_org),
):
    try:
        workflow = await workflow_engine.cancel_workflow(db, workflow_id, _require_org(org_id), current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _workflow_detail(workflow)


@router.post("/workflows/{workflow_id}/retry-step/{step_key}", response_model=LegalWorkflowDetail)
async def retry_step(
    workflow_id: int,
    step_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int | None = Depends(get_current_org),
):
    organization_id = _require_org(org_id)
    try:
        await workflow_engine.retry_step(db, workflow_id, organization_id, step_key, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    safe_task_delay(run_ai_drafting_step, workflow_id=workflow_id, organization_id=organization_id)
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return _workflow_detail(workflow)


@router.get("/workflows/{workflow_id}/events", response_model=List[WorkflowEvent])
async def get_workflow_events(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
    skip: int = 0,
    limit: int = 100,
):
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, _require_org(org_id))
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    result = await db.execute(
        select(DBWorkflowEvent)
        .where(DBWorkflowEvent.workflow_id == workflow_id)
        .order_by(DBWorkflowEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


# =============================================================================
# Draft Endpoints  (Milestone 7)
# =============================================================================

@router.get("/workflows/{workflow_id}/drafts", response_model=List[LegalDraft])
async def list_drafts(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
):
    """List all drafts for a workflow, newest first."""
    organization_id = _require_org(org_id)
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    result = await db.execute(
        select(DBLegalDraft)
        .where(DBLegalDraft.workflow_id == workflow_id, DBLegalDraft.organization_id == organization_id)
        .order_by(DBLegalDraft.version.desc(), DBLegalDraft.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/workflows/{workflow_id}/drafts", response_model=LegalDraft, status_code=status.HTTP_201_CREATED)
async def create_draft(
    workflow_id: int,
    draft_in: LegalDraftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int | None = Depends(get_current_org),
):
    """Manually create or attach a draft to a workflow."""
    organization_id = _require_org(org_id)
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    draft = await legal_workflow_crud.create_draft(db, workflow, draft_in, created_by_user_id=current_user.id)
    return draft


@router.patch("/drafts/{draft_id}", response_model=LegalDraft)
async def update_draft(
    draft_id: int,
    draft_in: LegalDraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int | None = Depends(get_current_org),
):
    """
    Autosave draft content. Supports optimistic versioning:
    if draft_in.version is provided and doesn't match current version,
    a new version is created instead of overwriting.
    """
    organization_id = _require_org(org_id)

    # Load existing draft
    result = await db.execute(
        select(DBLegalDraft).where(
            DBLegalDraft.id == draft_id,
            DBLegalDraft.organization_id == organization_id,
        )
    )
    draft = result.scalars().first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    # Optimistic version check: if client sends a version and it's stale, create new version
    if draft_in.version is not None and draft_in.version != draft.version:
        new_draft_in = LegalDraftCreate(
            title=draft_in.title or draft.title,
            content_json=draft_in.content_json or draft.content_json,
            content_text=draft_in.content_text or draft.content_text,
            html_snapshot=draft_in.html_snapshot or draft.html_snapshot,
            status=draft.status,
            editor_format=draft.editor_format,
            source_document_id=draft.source_document_id,
            created_by=getattr(current_user, "email", "user"),
        )
        workflow = await legal_workflow_crud.get_workflow(db, draft.workflow_id, organization_id)
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent workflow not found")
        new_draft = await legal_workflow_crud.create_draft(db, workflow, new_draft_in, created_by_user_id=current_user.id)
        new_draft.version = draft.version + 1
        new_draft.parent_draft_id = draft.id
        await db.commit()
        await db.refresh(new_draft)
        return new_draft

    # In-place update (autosave)
    updated = await legal_workflow_crud.update_draft(db, draft_id, organization_id, draft_in)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return updated


@router.post("/drafts/{draft_id}/approve", response_model=LegalDraft)
async def approve_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
    org_id: int | None = Depends(get_current_org),
):
    """
    Approve a draft. Sets approved fields, transitions workflow to
    APPROVED_FOR_ASSEMBLY, and publishes a WebSocket update.
    """
    organization_id = _require_org(org_id)
    draft = await legal_workflow_crud.approve_draft(db, draft_id, organization_id, current_user.id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    await workflow_engine.publish_workflow_update(
        db, draft.workflow_id, organization_id, "Draft approved – ready for bundle assembly"
    )
    return draft


@router.post("/drafts/{draft_id}/request-revision", response_model=LegalDraft)
async def request_revision(
    draft_id: int,
    body: DraftRevisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
    org_id: int | None = Depends(get_current_org),
):
    """
    Request a revision. Sets draft status to REVISION_REQUESTED and
    transitions workflow to REVISION_REQUESTED so AI can re-draft.
    """
    organization_id = _require_org(org_id)

    result = await db.execute(
        select(DBLegalDraft).where(
            DBLegalDraft.id == draft_id,
            DBLegalDraft.organization_id == organization_id,
        )
    )
    draft = result.scalars().first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    draft.status = LegalDraftStatus.REVISION_REQUESTED.value
    await db.flush()

    workflow = await legal_workflow_crud.get_workflow(db, draft.workflow_id, organization_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    try:
        await workflow_engine.transition_workflow(
            db,
            workflow,
            WFStatus.REVISION_REQUESTED.value,
            actor_user_id=current_user.id,
            event_type="draft.revision_requested",
            payload={"draft_id": draft.id, "instructions": body.instructions or ""},
        )
    except ValueError:
        pass  # Already in that state – not a fatal error

    if body.instructions:
        meta = dict(workflow.metadata_json or {})
        meta["drafting_instructions"] = body.instructions
        workflow.metadata_json = meta

    await db.commit()
    await db.refresh(draft)
    await workflow_engine.publish_workflow_update(
        db, draft.workflow_id, organization_id, "Revision requested"
    )
    return draft


# =============================================================================
# Bundle Endpoints  (Milestone 10)
# =============================================================================

@router.post("/workflows/{workflow_id}/bundle", response_model=CourtBundleSummary, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    workflow_id: int,
    bundle_in: CourtBundleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
    org_id: int | None = Depends(get_current_org),
):
    """Create a court bundle for an approved workflow."""
    organization_id = _require_org(org_id)
    workflow = await legal_workflow_crud.get_workflow(db, workflow_id, organization_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    if workflow.status not in {
        WFStatus.APPROVED_FOR_ASSEMBLY.value,
        WFStatus.ASSEMBLING_BUNDLE.value,
        WFStatus.ASSEMBLY_FAILED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bundle can only be created from APPROVED_FOR_ASSEMBLY state. Current: {workflow.status}",
        )
    bundle = await legal_workflow_crud.create_bundle(db, workflow, bundle_in)
    return bundle


@router.get("/bundles/{bundle_id}", response_model=CourtBundleSummary)
async def get_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
):
    """Get bundle status and manifest."""
    organization_id = _require_org(org_id)
    result = await db.execute(
        select(DBCourtBundle).where(
            DBCourtBundle.id == bundle_id,
            DBCourtBundle.organization_id == organization_id,
        )
    )
    bundle = result.scalars().first()
    if not bundle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
    return bundle


@router.post("/bundles/{bundle_id}/assemble", response_model=CourtBundleSummary)
async def assemble_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
    org_id: int | None = Depends(get_current_org),
):
    """Trigger bundle assembly (queues Celery task)."""
    organization_id = _require_org(org_id)
    result = await db.execute(
        select(DBCourtBundle).where(
            DBCourtBundle.id == bundle_id,
            DBCourtBundle.organization_id == organization_id,
        )
    )
    bundle = result.scalars().first()
    if not bundle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    bundle.status = CourtBundleStatus.ASSEMBLING.value

    # Transition workflow status to ASSEMBLING_BUNDLE
    workflow = await legal_workflow_crud.get_workflow(db, bundle.workflow_id, organization_id)
    if workflow:
        await workflow_engine.transition_workflow(
            db, workflow, WFStatus.ASSEMBLING_BUNDLE.value, actor_user_id=current_user.id
        )

    await db.commit()
    await db.refresh(bundle)

    safe_task_delay(run_bundle_assembly_step, workflow_id=bundle.workflow_id, organization_id=organization_id)
    return bundle


@router.get("/bundles/{bundle_id}/download")
async def download_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
):
    """Get download URL for the final bundle artifact."""
    organization_id = _require_org(org_id)
    result = await db.execute(
        select(DBCourtBundle).where(
            DBCourtBundle.id == bundle_id,
            DBCourtBundle.organization_id == organization_id,
        )
    )
    bundle = result.scalars().first()
    if not bundle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
    if bundle.status != CourtBundleStatus.READY.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bundle is not yet ready for download")
    if not bundle.final_artifact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final artifact not yet available")

    artifact_result = await db.execute(
        select(DBLegalArtifact).where(DBLegalArtifact.id == bundle.final_artifact_id)
    )
    artifact = artifact_result.scalars().first()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact record not found")

    return {
        "download_url": artifact.storage_url,
        "filename": artifact.filename,
        "size_bytes": artifact.size_bytes,
    }


@router.get("/bundles/{bundle_id}/chunks")
async def get_bundle_chunks(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int | None = Depends(get_current_org),
):
    """List all court-sized chunk artifacts for a bundle."""
    organization_id = _require_org(org_id)
    result = await db.execute(
        select(DBCourtBundle).where(
            DBCourtBundle.id == bundle_id,
            DBCourtBundle.organization_id == organization_id,
        )
    )
    bundle = result.scalars().first()
    if not bundle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    items_result = await db.execute(
        select(DBCourtBundleItem)
        .where(DBCourtBundleItem.bundle_id == bundle_id)
        .order_by(DBCourtBundleItem.sort_order)
    )
    items = list(items_result.scalars().all())
    return [
        {
            "id": item.id,
            "label": item.label,
            "item_type": item.item_type,
            "sort_order": item.sort_order,
            "artifact_id": item.artifact_id,
            "page_start": item.page_start,
            "page_end": item.page_end,
            "redaction_status": item.redaction_status,
        }
        for item in items
    ]
