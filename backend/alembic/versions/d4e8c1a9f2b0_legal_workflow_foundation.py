"""legal workflow foundation

Revision ID: d4e8c1a9f2b0
Revises: b9e4d2f1a7c3
Create Date: 2026-06-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e8c1a9f2b0"
down_revision: Union[str, Sequence[str], None] = "b9e4d2f1a7c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_workflows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("workflow_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_step_key", sa.String(), nullable=True),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("active_draft_id", sa.Integer(), nullable=True),
        sa.Column("final_bundle_id", sa.Integer(), nullable=True),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_workflows_assignee_status", "legal_workflows", ["assigned_user_id", "status"])
    op.create_index("ix_legal_workflows_case_status", "legal_workflows", ["case_id", "status"])
    op.create_index("ix_legal_workflows_org_status", "legal_workflows", ["organization_id", "status"])
    op.create_index("ix_legal_workflows_source_document", "legal_workflows", ["source_document_id"])

    op.create_table(
        "legal_workflow_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("depends_on", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("celery_task_id", sa.String(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("progress", sa.Numeric(), server_default="0", nullable=False),
        sa.Column("input_artifact_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("output_artifact_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["legal_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "step_key", name="uq_legal_workflow_steps_workflow_step_key"),
    )
    op.create_index("ix_legal_workflow_steps_step_key", "legal_workflow_steps", ["step_key"])
    op.create_index("ix_legal_workflow_steps_workflow_status", "legal_workflow_steps", ["workflow_id", "status"])

    op.create_table(
        "legal_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("checksum", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["legal_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_artifacts_case_type", "legal_artifacts", ["case_id", "artifact_type"])
    op.create_index("ix_legal_artifacts_workflow_type", "legal_artifacts", ["workflow_id", "artifact_type"])

    op.create_table(
        "legal_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("editor_format", sa.String(), server_default="tiptap_json", nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("html_snapshot", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("parent_draft_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["parent_draft_id"], ["legal_drafts.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["legal_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_drafts_case_created", "legal_drafts", ["case_id", "created_at"])
    op.create_index("ix_legal_drafts_workflow_status", "legal_drafts", ["workflow_id", "status"])

    op.create_table(
        "court_bundles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("approved_draft_id", sa.Integer(), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("court_profile", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("max_chunk_bytes", sa.BigInteger(), server_default=str(25 * 1024 * 1024), nullable=False),
        sa.Column("toc_artifact_id", sa.Integer(), nullable=True),
        sa.Column("final_artifact_id", sa.Integer(), nullable=True),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_draft_id"], ["legal_drafts.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["final_artifact_id"], ["legal_artifacts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["toc_artifact_id"], ["legal_artifacts.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["legal_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "court_bundle_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bundle_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("redaction_status", sa.String(), server_default="not_required", nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["legal_artifacts.id"]),
        sa.ForeignKeyConstraint(["bundle_id"], ["court_bundles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_court_bundle_items_bundle_order", "court_bundle_items", ["bundle_id", "sort_order"])

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["legal_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_events_workflow_created", "workflow_events", ["workflow_id", "created_at"])

    op.create_foreign_key(
        "fk_legal_workflows_active_draft_id",
        "legal_workflows",
        "legal_drafts",
        ["active_draft_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_legal_workflows_final_bundle_id",
        "legal_workflows",
        "court_bundles",
        ["final_bundle_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_legal_workflows_final_bundle_id", "legal_workflows", type_="foreignkey")
    op.drop_constraint("fk_legal_workflows_active_draft_id", "legal_workflows", type_="foreignkey")

    op.drop_index("ix_workflow_events_workflow_created", "workflow_events")
    op.drop_table("workflow_events")

    op.drop_index("ix_court_bundle_items_bundle_order", "court_bundle_items")
    op.drop_table("court_bundle_items")

    op.drop_table("court_bundles")

    op.drop_index("ix_legal_drafts_workflow_status", "legal_drafts")
    op.drop_index("ix_legal_drafts_case_created", "legal_drafts")
    op.drop_table("legal_drafts")

    op.drop_index("ix_legal_artifacts_workflow_type", "legal_artifacts")
    op.drop_index("ix_legal_artifacts_case_type", "legal_artifacts")
    op.drop_table("legal_artifacts")

    op.drop_index("ix_legal_workflow_steps_workflow_status", "legal_workflow_steps")
    op.drop_index("ix_legal_workflow_steps_step_key", "legal_workflow_steps")
    op.drop_table("legal_workflow_steps")

    op.drop_index("ix_legal_workflows_source_document", "legal_workflows")
    op.drop_index("ix_legal_workflows_org_status", "legal_workflows")
    op.drop_index("ix_legal_workflows_case_status", "legal_workflows")
    op.drop_index("ix_legal_workflows_assignee_status", "legal_workflows")
    op.drop_table("legal_workflows")
