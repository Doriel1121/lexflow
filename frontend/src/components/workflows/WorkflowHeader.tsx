/**
 * WorkflowHeader.tsx
 * Displays the workflow title, status badge, assigned user, and action buttons.
 */

import { Workflow } from "../../services/workflows";

interface Props {
  workflow: Workflow;
  onStart?: () => void;
  onCancel?: () => void;
  loading?: boolean;
}

const STATUS_LABELS: Record<string, string> = {
  CREATED: "Created",
  INTAKE_RECEIVED: "Intake Received",
  INGESTING: "Ingesting",
  INGESTION_FAILED: "Ingestion Failed",
  AI_ANALYZING: "AI Analyzing",
  AI_DRAFTING: "AI Drafting",
  AI_DRAFT_FAILED: "Draft Failed",
  PENDING_HUMAN_REVIEW: "Pending Review",
  IN_HUMAN_REVIEW: "In Review",
  REVISION_REQUESTED: "Revision Requested",
  APPROVED_FOR_ASSEMBLY: "Approved",
  ASSEMBLING_BUNDLE: "Assembling Bundle",
  ASSEMBLY_FAILED: "Assembly Failed",
  READY_FOR_COURT_SUBMISSION: "Ready for Court",
  SUBMITTED: "Submitted",
  ARCHIVED: "Archived",
  CANCELLED: "Cancelled",
};

const STATUS_COLORS: Record<string, string> = {
  CREATED: "bg-slate-100 text-slate-700",
  INTAKE_RECEIVED: "bg-blue-100 text-blue-700",
  INGESTING: "bg-blue-100 text-blue-700",
  INGESTION_FAILED: "bg-red-100 text-red-700",
  AI_ANALYZING: "bg-purple-100 text-purple-700",
  AI_DRAFTING: "bg-purple-100 text-purple-700",
  AI_DRAFT_FAILED: "bg-red-100 text-red-700",
  PENDING_HUMAN_REVIEW: "bg-amber-100 text-amber-700",
  IN_HUMAN_REVIEW: "bg-amber-100 text-amber-700",
  REVISION_REQUESTED: "bg-orange-100 text-orange-700",
  APPROVED_FOR_ASSEMBLY: "bg-green-100 text-green-700",
  ASSEMBLING_BUNDLE: "bg-cyan-100 text-cyan-700",
  ASSEMBLY_FAILED: "bg-red-100 text-red-700",
  READY_FOR_COURT_SUBMISSION: "bg-emerald-100 text-emerald-800",
  SUBMITTED: "bg-emerald-100 text-emerald-800",
  ARCHIVED: "bg-slate-100 text-slate-500",
  CANCELLED: "bg-slate-100 text-slate-500",
};

const ACTIVE_STATES = new Set([
  "AI_ANALYZING",
  "AI_DRAFTING",
  "INGESTING",
  "ASSEMBLING_BUNDLE",
  "INTAKE_RECEIVED",
]);

export function WorkflowHeader({ workflow, onStart, onCancel, loading }: Props) {
  const statusLabel = STATUS_LABELS[workflow.status] ?? workflow.status;
  const statusColor =
    STATUS_COLORS[workflow.status] ?? "bg-slate-100 text-slate-700";
  const isActive = ACTIVE_STATES.has(workflow.status);
  const canStart = workflow.status === "CREATED";
  const canCancel = !["SUBMITTED", "ARCHIVED", "CANCELLED"].includes(
    workflow.status
  );

  return (
    <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-200">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-xl font-semibold text-slate-900 truncate">
            Court Response Workflow
          </h1>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusColor}`}
          >
            {isActive && (
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
            )}
            {statusLabel}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Workflow #{workflow.id} · Case #{workflow.case_id}
          {workflow.current_step_key && (
            <span className="ml-2 font-mono text-xs text-slate-400">
              [{workflow.current_step_key}]
            </span>
          )}
        </p>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {canStart && (
          <button
            id="workflow-start-btn"
            onClick={onStart}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Starting…" : "Start Workflow"}
          </button>
        )}
        {canCancel && workflow.status !== "CREATED" && (
          <button
            id="workflow-cancel-btn"
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
