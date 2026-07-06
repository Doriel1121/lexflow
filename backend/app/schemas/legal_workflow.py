from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.legal_workflow_constants import (
    DEFAULT_COURT_BUNDLE_MAX_CHUNK_BYTES,
    DEFAULT_DRAFT_EDITOR_FORMAT,
    LegalDraftStatus,
    WorkflowActorType,
    WorkflowStatus,
    WorkflowType,
)


class LegalWorkflowCreate(BaseModel):
    case_id: int
    source_document_id: Optional[int] = None
    workflow_type: WorkflowType = WorkflowType.COURT_RESPONSE_BUNDLE
    assigned_user_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LegalWorkflowStep(BaseModel):
    id: int
    workflow_id: int
    step_key: str
    step_type: str
    status: str
    ordinal: int
    depends_on: List[str] = Field(default_factory=list)
    celery_task_id: Optional[str] = None
    attempt_count: int
    progress: float
    input_artifact_ids: List[int] = Field(default_factory=list)
    output_artifact_ids: List[int] = Field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LegalArtifactCreate(BaseModel):
    artifact_type: str
    filename: str
    document_id: Optional[int] = None
    storage_url: Optional[str] = None
    storage_key: Optional[str] = None
    mime_type: Optional[str] = None
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LegalArtifact(BaseModel):
    id: int
    organization_id: int
    case_id: int
    workflow_id: Optional[int] = None
    artifact_type: str
    document_id: Optional[int] = None
    storage_url: Optional[str] = None
    storage_key: Optional[str] = None
    mime_type: Optional[str] = None
    filename: str
    version: int
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
    created_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class LegalDraftCreate(BaseModel):
    title: str
    content_json: Dict[str, Any]
    content_text: Optional[str] = None
    html_snapshot: Optional[str] = None
    status: LegalDraftStatus = LegalDraftStatus.AI_GENERATED
    editor_format: str = DEFAULT_DRAFT_EDITOR_FORMAT
    source_document_id: Optional[int] = None
    created_by: str = "ai"


class LegalDraftUpdate(BaseModel):
    title: Optional[str] = None
    content_json: Optional[Dict[str, Any]] = None
    content_text: Optional[str] = None
    html_snapshot: Optional[str] = None
    status: Optional[LegalDraftStatus] = None
    version: Optional[int] = None


class LegalDraft(BaseModel):
    id: int
    organization_id: int
    case_id: int
    workflow_id: int
    source_document_id: Optional[int] = None
    status: str
    title: str
    editor_format: str
    content_json: Dict[str, Any]
    content_text: Optional[str] = None
    html_snapshot: Optional[str] = None
    version: int
    parent_draft_id: Optional[int] = None
    created_by: str
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourtBundleCreate(BaseModel):
    approved_draft_id: int
    jurisdiction: Optional[str] = None
    court_profile: Dict[str, Any] = Field(default_factory=dict)
    max_chunk_bytes: int = DEFAULT_COURT_BUNDLE_MAX_CHUNK_BYTES


class CourtBundleSummary(BaseModel):
    id: int
    workflow_id: int
    status: str
    approved_draft_id: int
    jurisdiction: Optional[str] = None
    max_chunk_bytes: int
    toc_artifact_id: Optional[int] = None
    final_artifact_id: Optional[int] = None
    manifest: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowEventCreate(BaseModel):
    event_type: str
    actor_type: WorkflowActorType = WorkflowActorType.SYSTEM
    step_key: Optional[str] = None
    actor_user_id: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEvent(BaseModel):
    id: int
    organization_id: int
    case_id: int
    workflow_id: int
    step_key: Optional[str] = None
    event_type: str
    actor_type: str
    actor_user_id: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class LegalWorkflow(BaseModel):
    id: int
    organization_id: int
    case_id: int
    workflow_type: str
    status: str
    current_step_key: Optional[str] = None
    source_document_id: Optional[int] = None
    active_draft_id: Optional[int] = None
    final_bundle_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    created_by_user_id: int
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
    error: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class LegalWorkflowDetail(LegalWorkflow):
    steps: List[LegalWorkflowStep] = Field(default_factory=list)
    drafts: List[LegalDraft] = Field(default_factory=list)
    bundle: Optional[CourtBundleSummary] = None
    recent_events: List[WorkflowEvent] = Field(default_factory=list)


class WorkflowStatusUpdate(BaseModel):
    status: WorkflowStatus
    current_step_key: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
