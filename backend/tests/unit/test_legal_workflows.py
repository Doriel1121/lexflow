import pytest
import fitz
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.legal_workflow_constants import (
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepKey,
    CourtBundleStatus,
)
from app.db.models.organization import Organization as DBOrganization
from app.db.models.user import User as DBUser, UserRole
from app.db.models.case import Case as DBCase
from app.db.models.document import Document as DBDocument
from app.db.models.legal_workflow import (
    LegalWorkflow,
    LegalWorkflowStep,
    LegalDraft,
    CourtBundle,
    CourtBundleItem,
    LegalArtifact,
)
from app.crud.legal_workflow import legal_workflow_crud
from app.schemas.legal_workflow import (
    LegalWorkflowCreate,
    LegalDraftCreate,
    CourtBundleCreate,
)
from app.services.workflow_engine import workflow_engine
from app.services.court_bundle_assembler import court_bundle_assembler, render_html_to_pdf


async def setup_test_org_user_case(db_session: AsyncSession):
    unique_suffix = uuid.uuid4().hex[:8]
    # Setup organization
    org = DBOrganization(name=f"Test Org {unique_suffix}", slug=f"test-org-{unique_suffix}")
    db_session.add(org)
    await db_session.flush()

    # Setup user
    user = DBUser(
        email=f"lawyer-{unique_suffix}@test.com",
        hashed_password="hashed_password",
        full_name="Test Lawyer",
        role=UserRole.LAWYER,
        organization_id=org.id,
    )
    db_session.add(user)
    await db_session.flush()

    # Setup case
    case = DBCase(
        title="Test Case",
        description="Test Case Description",
        created_by_user_id=user.id,
        organization_id=org.id,
    )
    db_session.add(case)
    await db_session.flush()

    await db_session.flush()
    return org, user, case


@pytest.mark.asyncio
async def test_workflow_creation_steps(db_session: AsyncSession):
    org, user, case = await setup_test_org_user_case(db_session)

    workflow_in = LegalWorkflowCreate(
        case_id=case.id,
        workflow_type="court_response_bundle",
    )
    
    workflow = await legal_workflow_crud.create_workflow(
        db_session, workflow_in, created_by_user_id=user.id, organization_id=org.id
    )

    assert workflow.id is not None
    assert workflow.status == WorkflowStatus.CREATED.value
    assert workflow.organization_id == org.id

    # Verify that steps were created automatically
    steps = await legal_workflow_crud.get_steps(db_session, workflow.id, org.id)
    assert len(steps) > 0
    assert steps[0].step_key == WorkflowStepKey.INTAKE_CAPTURE.value
    assert steps[0].status == WorkflowStepStatus.PENDING.value


@pytest.mark.asyncio
async def test_invalid_workflow_transition(db_session: AsyncSession):
    org, user, case = await setup_test_org_user_case(db_session)

    workflow_in = LegalWorkflowCreate(
        case_id=case.id,
        workflow_type="court_response_bundle",
    )
    workflow = await legal_workflow_crud.create_workflow(
        db_session, workflow_in, created_by_user_id=user.id, organization_id=org.id
    )

    # CREATED -> READY_FOR_COURT_SUBMISSION is invalid
    with pytest.raises(ValueError, match="Invalid workflow transition"):
        await workflow_engine.transition_workflow(
            db_session, workflow, WorkflowStatus.READY_FOR_COURT_SUBMISSION.value
        )


@pytest.mark.asyncio
async def test_step_retry_attempt_count(db_session: AsyncSession):
    org, user, case = await setup_test_org_user_case(db_session)

    workflow_in = LegalWorkflowCreate(
        case_id=case.id,
        workflow_type="court_response_bundle",
    )
    workflow = await legal_workflow_crud.create_workflow(
        db_session, workflow_in, created_by_user_id=user.id, organization_id=org.id
    )

    steps = await legal_workflow_crud.get_steps(db_session, workflow.id, org.id)
    step = steps[0]
    
    # Force step status to FAILED so it can be retried
    step.status = WorkflowStepStatus.FAILED.value
    step.attempt_count = 1
    await db_session.flush()

    # Retry the step
    updated_step = await workflow_engine.retry_step(
        db_session, workflow.id, org.id, step.step_key, user.id
    )

    assert updated_step.status == WorkflowStepStatus.PENDING.value
    assert updated_step.attempt_count == 1
    assert updated_step.error is None


@pytest.mark.asyncio
async def test_draft_approval_transitions_and_completes_steps(db_session: AsyncSession):
    org, user, case = await setup_test_org_user_case(db_session)

    workflow_in = LegalWorkflowCreate(
        case_id=case.id,
        workflow_type="court_response_bundle",
    )
    workflow = await legal_workflow_crud.create_workflow(
        db_session, workflow_in, created_by_user_id=user.id, organization_id=org.id
    )
    
    # Transition to IN_HUMAN_REVIEW to make draft approval transition valid
    workflow.status = WorkflowStatus.IN_HUMAN_REVIEW.value
    await db_session.flush()

    draft_in = LegalDraftCreate(
        title="Test Draft Response",
        content_json={"type": "doc", "content": []},
        content_text="Test response content",
        html_snapshot="<p>Test response content</p>",
        created_by=user.full_name,
    )
    draft = await legal_workflow_crud.create_draft(
        db_session, workflow, draft_in, created_by_user_id=user.id
    )

    # Approve draft
    approved = await legal_workflow_crud.approve_draft(
        db_session, draft.id, org.id, user.id
    )

    assert approved.status == "APPROVED"
    assert approved.approved_by_user_id == user.id
    
    # Workflow status should transition to APPROVED_FOR_ASSEMBLY
    assert approved.workflow.status == WorkflowStatus.APPROVED_FOR_ASSEMBLY.value
    
    # Human review steps should be marked as COMPLETED
    steps = await legal_workflow_crud.get_steps(db_session, workflow.id, org.id)
    human_steps = [s for s in steps if s.step_key in ("review.human_edit", "review.approve")]
    assert len(human_steps) == 2
    for step in human_steps:
        assert step.status == WorkflowStepStatus.COMPLETED.value
        assert step.completed_at is not None


@pytest.mark.asyncio
async def test_workflow_access_org_scoped(db_session: AsyncSession):
    org, user, case = await setup_test_org_user_case(db_session)

    # Setup a second organization
    other_org_suffix = uuid.uuid4().hex[:8]
    other_org = DBOrganization(name=f"Other Org {other_org_suffix}", slug=f"other-org-{other_org_suffix}")
    db_session.add(other_org)
    await db_session.flush()

    workflow_in = LegalWorkflowCreate(
        case_id=case.id,
        workflow_type="court_response_bundle",
    )
    workflow = await legal_workflow_crud.create_workflow(
        db_session, workflow_in, created_by_user_id=user.id, organization_id=org.id
    )

    # Attempt to access the workflow with the other org id
    with pytest.raises(ValueError, match="Workflow not found or not accessible"):
        await legal_workflow_crud._ensure_workflow_access(db_session, workflow.id, other_org.id)


@pytest.mark.asyncio
async def test_bundle_assembly_e2e(db_session: AsyncSession):
    org, user, case = await setup_test_org_user_case(db_session)

    # Create a source document in the case
    source_doc = DBDocument(
        filename="complaint.pdf",
        s3_url="http://localhost:8000/uploads/cases/1/complaint.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        organization_id=org.id,
    )
    db_session.add(source_doc)
    await db_session.flush()

    workflow_in = LegalWorkflowCreate(
        case_id=case.id,
        source_document_id=source_doc.id,
        workflow_type="court_response_bundle",
    )
    workflow = await legal_workflow_crud.create_workflow(
        db_session, workflow_in, created_by_user_id=user.id, organization_id=org.id
    )

    draft_in = LegalDraftCreate(
        title="Test Response Draft",
        content_json={"type": "doc", "content": []},
        content_text="This is a test response",
        html_snapshot="<h1>Court Response</h1><p>This is a test response draft statement.</p>",
        created_by=user.full_name,
    )
    draft = await legal_workflow_crud.create_draft(
        db_session, workflow, draft_in, created_by_user_id=user.id
    )
    
    # Set draft as approved
    draft.status = "APPROVED"
    draft.approved_by_user_id = user.id
    draft.approved_at = datetime.utcnow()
    workflow.status = WorkflowStatus.APPROVED_FOR_ASSEMBLY.value
    await db_session.flush()

    # Create the bundle record
    bundle_in = CourtBundleCreate(
        approved_draft_id=draft.id,
        max_chunk_bytes=100 * 1024,  # Use small limit to test chunking
    )
    bundle = await legal_workflow_crud.create_bundle(db_session, workflow, bundle_in)

    # Mock storage service and local file path resolution
    # Create real dummy PDF files for PyMuPDF to read/manipulate
    doc1 = fitz.open()
    doc1.new_page()
    doc1.new_page()  # 2 pages
    pdf1_bytes = doc1.tobytes()
    doc1.close()

    # Write dummy complaint PDF file to uploads dir mock location
    import os
    os.makedirs(os.path.join("uploads", "cases", "1"), exist_ok=True)
    complaint_path = os.path.join("uploads", "cases", "1", "complaint.pdf")
    with open(complaint_path, "wb") as f:
        f.write(pdf1_bytes)

    try:
        # Mock storage_service save_file_bytes to return fake URLs
        mock_save = MagicMock()
        async def fake_save(content: bytes, destination: str, filename: str):
            return f"http://localhost:8000/uploads/{destination}/{filename}", Path(os.path.join("uploads", destination, filename))
        
        with patch("app.services.court_bundle_assembler.storage_service.save_file_bytes", side_effect=fake_save):
            # Run bundle assembly
            assembled = await court_bundle_assembler.assemble_bundle(db_session, workflow.id, org.id)
            
            assert assembled.status == CourtBundleStatus.READY.value
            assert assembled.final_artifact_id is not None
            assert assembled.toc_artifact_id is not None
            assert len(assembled.items) > 0
            
            # Verify manifest
            assert assembled.manifest["total_pages"] > 0
            assert assembled.manifest["draft_pages"] > 0
            assert len(assembled.manifest["chunks"]) > 0

            # Verify workflow step statuses
            steps = await legal_workflow_crud.get_steps(db_session, workflow.id, org.id)
            bundle_steps = [s for s in steps if s.step_key.startswith("bundle.")]
            for s in bundle_steps:
                assert s.status == WorkflowStepStatus.COMPLETED.value

            # Verify workflow status
            assert workflow.status == WorkflowStatus.READY_FOR_COURT_SUBMISSION.value
    finally:
        # Clean up files
        if os.path.exists(complaint_path):
            os.remove(complaint_path)
