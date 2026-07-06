/**
 * useWorkflow.ts
 * React hook for fetching and managing a single workflow's state,
 * with polling fallback when WebSocket is disconnected.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import workflowsApi, { Workflow } from "../services/workflows";

const POLL_INTERVAL_MS = 5000;

// States where we should NOT poll (workflow is resting)
const TERMINAL_STATES = new Set([
  "PENDING_HUMAN_REVIEW",
  "IN_HUMAN_REVIEW",
  "APPROVED_FOR_ASSEMBLY",
  "READY_FOR_COURT_SUBMISSION",
  "SUBMITTED",
  "CANCELLED",
  "ARCHIVED",
]);

interface UseWorkflowResult {
  workflow: Workflow | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useWorkflow(
  workflowId: number | null,
  wsConnected: boolean
): UseWorkflowResult {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetch = useCallback(async () => {
    if (!workflowId) return;
    try {
      const data = await workflowsApi.getWorkflow(workflowId);
      setWorkflow(data);
      setError(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load workflow");
    }
  }, [workflowId]);

  // Initial load
  useEffect(() => {
    if (!workflowId) return;
    setLoading(true);
    fetch().finally(() => setLoading(false));
  }, [workflowId, fetch]);

  // Polling fallback when WebSocket is disconnected and workflow is active
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    if (!workflowId) return;
    if (wsConnected) return; // WebSocket is live — no polling needed
    if (workflow && TERMINAL_STATES.has(workflow.status)) return; // Don't poll resting states

    pollRef.current = setInterval(() => {
      fetch();
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [workflowId, wsConnected, workflow?.status, fetch]);

  return { workflow, loading, error, refresh: fetch };
}
