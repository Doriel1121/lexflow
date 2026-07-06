/**
 * useWorkflowSocket.ts
 * Hook that subscribes to workflow WebSocket events from the global WebSocket manager.
 */

import { useEffect, useState } from "react";
import WebSocketManager from "../services/websocketManager";

export type WorkflowSocketEvent =
  | { type: "workflow_status_update"; workflow_id: number; status: string; current_step_key: string | null; progress?: number; message?: string }
  | { type: "workflow_step_update"; workflow_id: number; step_key: string; step_status: string; progress?: number }
  | { type: "draft_updated"; workflow_id: number; draft_id: number }
  | { type: "bundle_ready"; workflow_id: number; bundle_id: number }
  | { type: "bundle_failed"; workflow_id: number; error: string };

interface UseWorkflowSocketResult {
  connected: boolean;
  lastEvent: WorkflowSocketEvent | null;
}

/**
 * Subscribes to workflow-related WebSocket messages for a specific workflow ID.
 * Also extends the global WebSocket manager to dispatch custom DOM events.
 */
export function useWorkflowSocket(
  workflowId: number | null,
  onUpdate?: (event: WorkflowSocketEvent) => void
): UseWorkflowSocketResult {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WorkflowSocketEvent | null>(null);

  useEffect(() => {
    // Track WebSocket connection state
    const unsubConn = WebSocketManager.onConnectionStateChange((isConnected) => {
      setConnected(isConnected);
    });

    return unsubConn;
  }, []);

  useEffect(() => {
    if (!workflowId) return;

    const unsubMsg = WebSocketManager.onMessage((data: any) => {
      // Map backend event types to frontend workflow events
      let event: WorkflowSocketEvent | null = null;

      if (
        data.type === "WORKFLOW_STATUS_UPDATE" &&
        data.workflow_id === workflowId
      ) {
        event = {
          type: "workflow_status_update",
          workflow_id: data.workflow_id,
          status: data.status,
          current_step_key: data.current_step_key ?? null,
          progress: data.progress,
          message: data.message,
        };

        // Dispatch custom DOM event for broader listeners
        window.dispatchEvent(
          new CustomEvent("workflow_status_update", { detail: data })
        );
      } else if (
        data.type === "WORKFLOW_STEP_UPDATE" &&
        data.workflow_id === workflowId
      ) {
        event = {
          type: "workflow_step_update",
          workflow_id: data.workflow_id,
          step_key: data.step_key,
          step_status: data.step_status,
          progress: data.progress,
        };
        window.dispatchEvent(
          new CustomEvent("workflow_step_update", { detail: data })
        );
      } else if (
        data.type === "DRAFT_UPDATED" &&
        data.workflow_id === workflowId
      ) {
        event = {
          type: "draft_updated",
          workflow_id: data.workflow_id,
          draft_id: data.draft_id,
        };
        window.dispatchEvent(new CustomEvent("draft_updated", { detail: data }));
      } else if (
        data.type === "BUNDLE_READY" &&
        data.workflow_id === workflowId
      ) {
        event = {
          type: "bundle_ready",
          workflow_id: data.workflow_id,
          bundle_id: data.bundle_id,
        };
        window.dispatchEvent(new CustomEvent("bundle_ready", { detail: data }));
      } else if (
        data.type === "BUNDLE_FAILED" &&
        data.workflow_id === workflowId
      ) {
        event = {
          type: "bundle_failed",
          workflow_id: data.workflow_id,
          error: data.error,
        };
        window.dispatchEvent(new CustomEvent("bundle_failed", { detail: data }));
      }

      if (event) {
        setLastEvent(event);
        onUpdate?.(event);
      }
    });

    return unsubMsg;
  }, [workflowId, onUpdate]);

  return { connected, lastEvent };
}
