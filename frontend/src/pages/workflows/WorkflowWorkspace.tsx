/**
 * WorkflowWorkspace.tsx
 * Main page for the workflow workspace: /cases/:caseId/workflows/:workflowId
 * Orchestrates all workflow components with live WebSocket updates.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useWorkflow } from "../../hooks/useWorkflow";
import { useWorkflowSocket } from "../../hooks/useWorkflowSocket";
import { WorkflowHeader } from "../../components/workflows/WorkflowHeader";
import { WorkflowStepper } from "../../components/workflows/WorkflowStepper";
import { WorkflowActivityRail } from "../../components/workflows/WorkflowActivityRail";
import { SplitReviewWorkspace } from "../../components/workflows/SplitReviewWorkspace";
import { BundleAssemblyPanel } from "../../components/workflows/BundleAssemblyPanel";
import workflowsApi, {
  CourtBundleSummary,
  LegalDraft,
} from "../../services/workflows";
import WebSocketManager from "../../services/websocketManager";

export default function WorkflowWorkspace() {
  const { caseId, workflowId } = useParams<{
    caseId: string;
    workflowId: string;
  }>();
  const navigate = useNavigate();
  const parsedWorkflowId = workflowId ? parseInt(workflowId, 10) : null;

  const [wsConnected, setWsConnected] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // WebSocket connection state
  useEffect(() => {
    const unsub = WebSocketManager.onConnectionStateChange((c) =>
      setWsConnected(c)
    );
    return unsub;
  }, []);

  // Core workflow state
  const { workflow, loading, error, refresh } = useWorkflow(
    parsedWorkflowId,
    wsConnected
  );

  // WebSocket events → refresh workflow
  const handleSocketEvent = useCallback(() => {
    refresh();
  }, [refresh]);

  useWorkflowSocket(parsedWorkflowId, handleSocketEvent);

  // Active draft from the workflow
  const activeDraft: LegalDraft | null =
    workflow?.active_draft_id
      ? (workflow.drafts.find((d) => d.id === workflow.active_draft_id) ??
        workflow.drafts[0] ??
        null)
      : workflow?.drafts?.[0] ?? null;

  // ── Actions ──────────────────────────────────────────────────────────────

  const handleStart = useCallback(async () => {
    if (!parsedWorkflowId) return;
    setActionLoading(true);
    try {
      await workflowsApi.startWorkflow(parsedWorkflowId);
      await refresh();
    } finally {
      setActionLoading(false);
    }
  }, [parsedWorkflowId, refresh]);

  const handleCancel = useCallback(async () => {
    if (!parsedWorkflowId) return;
    if (!confirm("Cancel this workflow?")) return;
    setActionLoading(true);
    try {
      await workflowsApi.cancelWorkflow(parsedWorkflowId);
      await refresh();
    } finally {
      setActionLoading(false);
    }
  }, [parsedWorkflowId, refresh]);

  const handleRetryStep = useCallback(
    async (stepKey: string) => {
      if (!parsedWorkflowId) return;
      setActionLoading(true);
      try {
        await workflowsApi.retryStep(parsedWorkflowId, stepKey);
        await refresh();
      } finally {
        setActionLoading(false);
      }
    },
    [parsedWorkflowId, refresh]
  );

  const handleDraftApproved = useCallback(async () => {
    await refresh();
  }, [refresh]);

  const handleRevisionRequested = useCallback(async () => {
    await refresh();
  }, [refresh]);

  const handleDraftSaved = useCallback(
    (_draft: LegalDraft) => {
      // Refresh lightly to sync version number
      refresh();
    },
    [refresh]
  );

  const handleBundleUpdated = useCallback(
    (_bundle: CourtBundleSummary) => {
      refresh();
    },
    [refresh]
  );

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading && !workflow) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin" />
          <p className="text-sm text-slate-500">Loading workflow…</p>
        </div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-center">
          <p className="text-red-600 font-medium mb-2">
            {error || "Workflow not found"}
          </p>
          <button
            onClick={() => navigate(`/cases/${caseId}`)}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Case
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Page container */}
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-5">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-slate-500">
          <button
            onClick={() => navigate("/cases")}
            className="hover:text-slate-700"
          >
            Cases
          </button>
          <span>/</span>
          <button
            onClick={() => navigate(`/cases/${caseId}`)}
            className="hover:text-slate-700"
          >
            Case #{caseId}
          </button>
          <span>/</span>
          <span className="text-slate-800 font-medium">
            Workflow #{workflow.id}
          </span>
        </nav>

        {/* Header */}
        <div className="bg-white rounded-xl border border-slate-200 px-6 py-4">
          <WorkflowHeader
            workflow={workflow}
            onStart={handleStart}
            onCancel={handleCancel}
            loading={actionLoading}
          />
        </div>

        {/* Pipeline stepper */}
        <WorkflowStepper
          workflow={workflow}
          onRetryStep={handleRetryStep}
        />

        {/* Error display */}
        {workflow.error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm font-medium text-red-700">
              Workflow Error
            </p>
            <pre className="mt-1 text-xs text-red-600 whitespace-pre-wrap">
              {JSON.stringify(workflow.error, null, 2)}
            </pre>
          </div>
        )}

        {/* Split review workspace (shown in review states) */}
        <SplitReviewWorkspace
          workflow={workflow}
          draft={activeDraft}
          documentUrl={null} /* TODO: fetch from document API */
          documentOcrText={null} /* TODO: fetch from document content */
          documentFilename={null}
          onDraftApproved={handleDraftApproved}
          onRevisionRequested={handleRevisionRequested}
          onDraftSaved={handleDraftSaved}
        />

        {/* Bundle assembly panel */}
        <BundleAssemblyPanel
          workflow={workflow}
          bundle={workflow.bundle}
          onBundleUpdated={handleBundleUpdated}
        />

        {/* Activity rail */}
        <WorkflowActivityRail events={workflow.recent_events} />

        {/* WebSocket status indicator */}
        <div className="flex justify-end">
          <span
            className={`inline-flex items-center gap-1.5 text-xs ${
              wsConnected ? "text-emerald-600" : "text-amber-500"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                wsConnected ? "bg-emerald-500" : "bg-amber-400"
              }`}
            />
            {wsConnected ? "Live" : "Polling (5s)"}
          </span>
        </div>
      </div>
    </div>
  );
}
