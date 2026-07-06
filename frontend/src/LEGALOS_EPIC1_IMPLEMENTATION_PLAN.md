# LegalOS Epic 1 Implementation Plan

## Goal

Implement the Unified Zero-Friction Workspace Workflow as a database-backed workflow engine, async worker pipeline, split-screen review workspace, and court bundle assembly system.

This plan is intentionally incremental. Each milestone should leave the app runnable and testable.

## Milestone 0: Prep and Guardrails

### Tasks

1. Confirm naming:
   - Use `legal_workflows`, `legal_workflow_steps`, `legal_artifacts`, `legal_drafts`, `court_bundles`, `court_bundle_items`, and `workflow_events`.

2. Confirm first workflow type:
   - `court_response_bundle`

3. Confirm MVP court bundle constraints:
   - Default max chunk size: 25 MB unless configured.
   - Redaction MVP: AI-suggested plus lawyer-approved redaction list.
   - Draft format: TipTap JSON.

4. Add backend constants:
   - Workflow status.
   - Step status.
   - Step keys.
   - Artifact types.

### Deliverables

- Constants module or enum definitions.
- No schema changes yet.

## Milestone 1: Database Foundation

### Tasks

1. Create SQLAlchemy models:
   - `backend/app/db/models/legal_workflow.py`

2. Add models:
   - `LegalWorkflow`
   - `LegalWorkflowStep`
   - `LegalArtifact`
   - `LegalDraft`
   - `CourtBundle`
   - `CourtBundleItem`
   - `WorkflowEvent`

3. Register models:
   - Update `backend/app/db/models/__init__.py`.

4. Create Alembic migration:
   - Add all new tables.
   - Add indexes.
   - Add foreign keys.

5. Run migration:
   - `alembic upgrade head` inside the backend container or local environment.

### Acceptance Criteria

- New tables exist.
- Existing document/case APIs still work.
- Alembic has one new migration with reversible downgrade.

## Milestone 2: Schemas and CRUD Layer

### Tasks

1. Add Pydantic schemas:
   - `backend/app/schemas/legal_workflow.py`

2. Add CRUD module:
   - `backend/app/crud/legal_workflow.py`

3. CRUD functions:
   - `create_workflow`
   - `get_workflow`
   - `list_case_workflows`
   - `create_default_steps`
   - `get_steps`
   - `create_event`
   - `create_artifact`
   - `create_draft`
   - `update_draft`
   - `approve_draft`

4. Add organization-aware access checks.

### Acceptance Criteria

- Unit tests can create workflow rows and default steps.
- Draft rows can be created and updated.
- Workflow retrieval includes steps, drafts, bundle summary, and recent events.

## Milestone 3: Workflow Engine Service

### Tasks

1. Create:
   - `backend/app/services/workflow_engine.py`

2. Implement:
   - `create_workflow`
   - `advance_workflow`
   - `claim_next_step`
   - `start_step`
   - `complete_step`
   - `fail_step`
   - `transition_workflow`
   - `publish_workflow_update`

3. Add event logging to all transitions.

4. Use row-level locking for step claims:
   - `FOR UPDATE SKIP LOCKED`

5. Add idempotency:
   - If expected output exists, complete the step instead of duplicating work.

### Acceptance Criteria

- Workflow can move from `CREATED` to `PENDING_HUMAN_REVIEW` through mocked automated steps.
- Duplicate worker execution does not create duplicate drafts/artifacts.
- Each transition writes `workflow_events`.

## Milestone 4: Workflow API

### Tasks

1. Create:
   - `backend/app/api/v1/endpoints/workflows.py`

2. Register router in:
   - `backend/app/api/v1/endpoints/__init__.py`

3. Implement endpoints:

```text
POST   /api/v1/workflows
GET    /api/v1/workflows/{workflow_id}
GET    /api/v1/cases/{case_id}/workflows
POST   /api/v1/workflows/{workflow_id}/start
POST   /api/v1/workflows/{workflow_id}/cancel
POST   /api/v1/workflows/{workflow_id}/retry-step/{step_key}
GET    /api/v1/workflows/{workflow_id}/events
```

4. Add request schema for workflow creation:

```json
{
  "case_id": 123,
  "source_document_id": 456,
  "workflow_type": "court_response_bundle",
  "assigned_user_id": 7,
  "metadata": {
    "jurisdiction": "israel",
    "court_profile": {}
  }
}
```

### Acceptance Criteria

- A workflow can be created from the API.
- A case can list its workflows.
- A workflow detail response returns current state and steps.

## Milestone 5: Celery Workflow Workers

### Tasks

1. Create:
   - `backend/app/workers/workflow_tasks.py`

2. Update `backend/app/core/celery.py`:
   - Include `app.workers.workflow_tasks`.

3. Implement tasks:

```text
start_workflow_task
run_ai_drafting_step
run_bundle_assembly_step
retry_workflow_step
```

4. Wire API `POST /workflows/{id}/start` to queue `start_workflow_task`.

5. Add task failure handling:
   - Mark step `FAILED`.
   - Mark workflow `AI_DRAFT_FAILED` or `ASSEMBLY_FAILED`.
   - Store structured error.
   - Publish WebSocket event.

### Acceptance Criteria

- Starting a workflow queues a Celery task.
- Worker updates workflow and step status.
- Failures are visible in API response and WebSocket payloads.

## Milestone 6: Draft Generation

### Tasks

1. Create:
   - `backend/app/services/legal_drafting.py`

2. Build draft input collector:
   - Source document OCR text.
   - Document intelligence.
   - Case details.
   - Deadlines if relevant.
   - Optional workflow metadata instructions.

3. Generate a legal response draft.

4. Convert AI output to TipTap JSON.

5. Store draft in `legal_drafts`.

6. Mark workflow:
   - `AI_DRAFTING` -> `PENDING_HUMAN_REVIEW`

### Acceptance Criteria

- Workflow creates an AI draft.
- Draft has `content_json`, `content_text`, and `html_snapshot`.
- Frontend can fetch the draft.

## Milestone 7: Draft APIs

### Tasks

1. Add endpoints:

```text
GET    /api/v1/workflows/{workflow_id}/drafts
POST   /api/v1/workflows/{workflow_id}/drafts
PATCH  /api/v1/drafts/{draft_id}
POST   /api/v1/drafts/{draft_id}/approve
POST   /api/v1/drafts/{draft_id}/request-revision
```

2. Implement optimistic draft saving:
   - Accept version in request.
   - Reject stale updates or create new version.

3. On approval:
   - Set draft `approved`.
   - Set `approved_by_user_id`.
   - Set `approved_at`.
   - Set workflow `APPROVED_FOR_ASSEMBLY`.
   - Queue assembly if requested.

### Acceptance Criteria

- Draft autosave works.
- Draft approval advances workflow.
- Approved draft is immutable or versioned.

## Milestone 8: Frontend Workflow Shell

### Tasks

1. Add service:
   - `frontend/src/services/workflows.ts`

2. Add hooks:
   - `frontend/src/hooks/useWorkflow.ts`
   - `frontend/src/hooks/useWorkflowSocket.ts`

3. Add page:
   - `frontend/src/pages/workflows/WorkflowWorkspace.tsx`

4. Add route:
   - `/cases/:caseId/workflows/:workflowId`

5. Add components:
   - `WorkflowHeader`
   - `WorkflowStepper`
   - `WorkflowActivityRail`

6. Extend WebSocket manager to dispatch:
   - `workflow_status_update`
   - `workflow_step_update`
   - `draft_updated`
   - `bundle_ready`
   - `bundle_failed`

### Acceptance Criteria

- User can open workflow workspace.
- Workflow status updates live.
- Polling fallback works when WebSocket is disconnected.

## Milestone 9: Split-Screen Review Workspace

### Tasks

1. Install TipTap packages:

```text
@tiptap/react
@tiptap/starter-kit
@tiptap/extension-placeholder
@tiptap/extension-text-align
@tiptap/extension-table
@tiptap/extension-link
@tiptap/extension-underline
@tiptap/extension-highlight
```

2. Create:
   - `SplitReviewWorkspace.tsx`
   - `PdfReviewPane.tsx`
   - `DraftEditorPane.tsx`

3. MVP PDF pane:
   - Use iframe for PDFs.
   - Use OCR text fallback for non-PDFs.

4. Editor pane:
   - Load TipTap JSON.
   - Debounced autosave.
   - Dirty/saved indicator.
   - Approve button.

5. Add review state transitions:
   - `PENDING_HUMAN_REVIEW` -> `IN_HUMAN_REVIEW`
   - `IN_HUMAN_REVIEW` -> `APPROVED_FOR_ASSEMBLY`

### Acceptance Criteria

- Lawyer can review original document and edit draft side by side.
- Autosave persists editor JSON.
- Approval button advances workflow.

## Milestone 10: Court Bundle Assembly Backend

### Tasks

1. Add dependencies:
   - `PyMuPDF`
   - `reportlab`
   - Optional: `pikepdf`

2. Create:
   - `backend/app/services/court_bundle_assembler.py`

3. Implement MVP assembly:
   - Render draft HTML to PDF.
   - Collect attachments.
   - Merge PDFs.
   - Generate TOC.
   - Add page numbers.
   - Split by max bytes.
   - Persist artifacts.
   - Persist manifest.

4. Add bundle APIs:

```text
POST   /api/v1/workflows/{workflow_id}/bundle
GET    /api/v1/bundles/{bundle_id}
POST   /api/v1/bundles/{bundle_id}/assemble
GET    /api/v1/bundles/{bundle_id}/download
GET    /api/v1/bundles/{bundle_id}/chunks
```

5. Add failure handling:
   - `ASSEMBLY_FAILED`
   - Step error with reason.
   - Bundle error with actionable details.

### Acceptance Criteria

- Approved draft can become a merged final PDF.
- Bundle chunks are generated under max byte limit.
- Manifest contains file names, sizes, and page ranges.

## Milestone 11: Bundle UI

### Tasks

1. Create:
   - `BundleAssemblyPanel.tsx`

2. Show:
   - Current assembly status.
   - Checklist of assembly stages.
   - Final PDF download.
   - Chunk downloads.
   - Manifest summary.
   - Assembly errors.

3. Add action:
   - Start assembly.
   - Retry failed assembly.

### Acceptance Criteria

- User can see bundle progress.
- User can download final bundle and chunked court files.
- Failed assembly can be retried from UI.

## Milestone 12: Case Integration

### Tasks

1. Update `CaseDetailPage.tsx`:
   - Add "Start Court Response Workflow" action near documents.
   - Add workflow list/status summary.

2. On document row:
   - Show "Create Response" for processed documents.

3. On workflow row:
   - Navigate to `/cases/:caseId/workflows/:workflowId`.

### Acceptance Criteria

- Workflow entry point is discoverable from a case.
- Existing case/document functionality remains intact.

## Milestone 13: Tests and Hardening

### Backend Tests

1. Workflow creation creates default steps.
2. Invalid transition is rejected.
3. Step retry increments attempt count.
4. AI draft generation persists draft.
5. Draft approval advances workflow.
6. Bundle chunking respects max bytes.
7. Workflow access is organization-scoped.

### Frontend Tests

1. Workflow workspace renders loading, active, failed, and ready states.
2. Split review loads source document and draft.
3. Autosave calls draft API.
4. Approve action calls approve endpoint.
5. WebSocket workflow event updates visible status.

### Operational Hardening

1. Add structured logs for workflow ID and step key.
2. Add dead-letter behavior for permanently failed tasks.
3. Add admin-facing error details.
4. Ensure storage cleanup for failed partial bundle artifacts.

## Suggested Build Order

1. Database migration.
2. Backend models, schemas, CRUD.
3. Workflow engine service.
4. Workflow API.
5. Celery workflow tasks with mocked draft output.
6. Frontend workflow shell.
7. Draft generation service.
8. TipTap split review.
9. Draft approval.
10. Bundle assembler.
11. Bundle UI.
12. Tests and hardening.

## Definition of Done

- Epic workflow can be created from a case document.
- Workflow state is persisted and observable.
- AI draft is generated and editable.
- Lawyer can approve the draft.
- Bundle assembly runs asynchronously.
- Final PDF and court-sized chunks are stored as artifacts.
- WebSocket updates keep the UI current.
- Failed automated steps can be retried.
- Workflow events provide an audit trail.

