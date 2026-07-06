from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.legal_workflow_constants import DEFAULT_COURT_BUNDLE_MAX_CHUNK_BYTES
from app.db.base import Base


class LegalWorkflow(Base):
    __tablename__ = "legal_workflows"
    __table_args__ = (
        Index("ix_legal_workflows_org_status", "organization_id", "status"),
        Index("ix_legal_workflows_case_status", "case_id", "status"),
        Index("ix_legal_workflows_source_document", "source_document_id"),
        Index("ix_legal_workflows_assignee_status", "assigned_user_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    workflow_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    current_step_key = Column(String, nullable=True)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    active_draft_id = Column(Integer, ForeignKey("legal_drafts.id"), nullable=True)
    final_bundle_id = Column(Integer, ForeignKey("court_bundles.id"), nullable=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)
    error = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", backref="legal_workflows")
    case = relationship("Case", backref="legal_workflows")
    source_document = relationship("Document", foreign_keys=[source_document_id], backref="source_workflows")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id], backref="assigned_legal_workflows")
    created_by = relationship("User", foreign_keys=[created_by_user_id], backref="created_legal_workflows")
    steps = relationship("LegalWorkflowStep", back_populates="workflow", cascade="all, delete-orphan")
    artifacts = relationship("LegalArtifact", back_populates="workflow")
    drafts = relationship(
        "LegalDraft",
        back_populates="workflow",
        cascade="all, delete-orphan",
        foreign_keys="LegalDraft.workflow_id",
    )
    active_draft = relationship("LegalDraft", foreign_keys=[active_draft_id], post_update=True)
    bundles = relationship(
        "CourtBundle",
        back_populates="workflow",
        cascade="all, delete-orphan",
        foreign_keys="CourtBundle.workflow_id",
    )
    final_bundle = relationship("CourtBundle", foreign_keys=[final_bundle_id], post_update=True)
    events = relationship("WorkflowEvent", back_populates="workflow", cascade="all, delete-orphan")


class LegalWorkflowStep(Base):
    __tablename__ = "legal_workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_key", name="uq_legal_workflow_steps_workflow_step_key"),
        Index("ix_legal_workflow_steps_workflow_status", "workflow_id", "status"),
        Index("ix_legal_workflow_steps_step_key", "step_key"),
    )

    id = Column(Integer, primary_key=True)
    workflow_id = Column(Integer, ForeignKey("legal_workflows.id", ondelete="CASCADE"), nullable=False)
    step_key = Column(String, nullable=False)
    step_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    ordinal = Column(Integer, nullable=False)
    depends_on = Column(JSONB, default=list, nullable=False)
    celery_task_id = Column(String, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    progress = Column(Numeric, default=0, nullable=False)
    input_artifact_ids = Column(JSONB, default=list, nullable=False)
    output_artifact_ids = Column(JSONB, default=list, nullable=False)
    error = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    workflow = relationship("LegalWorkflow", back_populates="steps")


class LegalArtifact(Base):
    __tablename__ = "legal_artifacts"
    __table_args__ = (
        Index("ix_legal_artifacts_workflow_type", "workflow_id", "artifact_type"),
        Index("ix_legal_artifacts_case_type", "case_id", "artifact_type"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("legal_workflows.id"), nullable=True)
    artifact_type = Column(String, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    storage_url = Column(Text, nullable=True)
    storage_key = Column(Text, nullable=True)
    mime_type = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    checksum = Column(String, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", backref="legal_artifacts")
    case = relationship("Case", backref="legal_artifacts")
    workflow = relationship("LegalWorkflow", back_populates="artifacts")
    document = relationship("Document", backref="legal_artifacts")
    created_by = relationship("User", backref="created_legal_artifacts")


class LegalDraft(Base):
    __tablename__ = "legal_drafts"
    __table_args__ = (
        Index("ix_legal_drafts_workflow_status", "workflow_id", "status"),
        Index("ix_legal_drafts_case_created", "case_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("legal_workflows.id"), nullable=False)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    status = Column(String, nullable=False)
    title = Column(String, nullable=False)
    editor_format = Column(String, default="tiptap_json", nullable=False)
    content_json = Column(JSONB, nullable=False)
    content_text = Column(Text, nullable=True)
    html_snapshot = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    parent_draft_id = Column(Integer, ForeignKey("legal_drafts.id"), nullable=True)
    created_by = Column(String, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", backref="legal_drafts")
    case = relationship("Case", backref="legal_drafts")
    workflow = relationship("LegalWorkflow", back_populates="drafts", foreign_keys=[workflow_id])
    source_document = relationship("Document", backref="legal_drafts")
    parent_draft = relationship("LegalDraft", remote_side=[id], backref="revisions")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id], backref="created_legal_drafts")
    approved_by_user = relationship("User", foreign_keys=[approved_by_user_id], backref="approved_legal_drafts")


class CourtBundle(Base):
    __tablename__ = "court_bundles"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("legal_workflows.id"), nullable=False)
    status = Column(String, nullable=False)
    approved_draft_id = Column(Integer, ForeignKey("legal_drafts.id"), nullable=False)
    jurisdiction = Column(String, nullable=True)
    court_profile = Column(JSONB, default=dict, nullable=False)
    max_chunk_bytes = Column(BigInteger, default=DEFAULT_COURT_BUNDLE_MAX_CHUNK_BYTES, nullable=False)
    toc_artifact_id = Column(Integer, ForeignKey("legal_artifacts.id"), nullable=True)
    final_artifact_id = Column(Integer, ForeignKey("legal_artifacts.id"), nullable=True)
    manifest = Column(JSONB, default=dict, nullable=False)
    error = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", backref="court_bundles")
    case = relationship("Case", backref="court_bundles")
    workflow = relationship("LegalWorkflow", back_populates="bundles", foreign_keys=[workflow_id])
    approved_draft = relationship("LegalDraft", foreign_keys=[approved_draft_id], backref="court_bundles")
    toc_artifact = relationship("LegalArtifact", foreign_keys=[toc_artifact_id])
    final_artifact = relationship("LegalArtifact", foreign_keys=[final_artifact_id])
    items = relationship("CourtBundleItem", back_populates="bundle", cascade="all, delete-orphan")


class CourtBundleItem(Base):
    __tablename__ = "court_bundle_items"
    __table_args__ = (Index("ix_court_bundle_items_bundle_order", "bundle_id", "sort_order"),)

    id = Column(Integer, primary_key=True)
    bundle_id = Column(Integer, ForeignKey("court_bundles.id", ondelete="CASCADE"), nullable=False)
    artifact_id = Column(Integer, ForeignKey("legal_artifacts.id"), nullable=False)
    item_type = Column(String, nullable=False)
    label = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    redaction_status = Column(String, default="not_required", nullable=False)
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)

    bundle = relationship("CourtBundle", back_populates="items")
    artifact = relationship("LegalArtifact", backref="court_bundle_items")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_workflow_created", "workflow_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("legal_workflows.id"), nullable=False)
    step_key = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    payload = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", backref="workflow_events")
    case = relationship("Case", backref="workflow_events")
    workflow = relationship("LegalWorkflow", back_populates="events")
    actor_user = relationship("User", backref="workflow_events")
