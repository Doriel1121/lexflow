/**
 * workflows.ts
 * API service layer for the LegalOS Workflow Engine.
 */

import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ─── Types ────────────────────────────────────────────────────────────────

export type WorkflowStatus =
  | "CREATED"
  | "INTAKE_RECEIVED"
  | "INGESTING"
  | "INGESTION_FAILED"
  | "AI_ANALYZING"
  | "AI_DRAFTING"
  | "AI_DRAFT_FAILED"
  | "PENDING_HUMAN_REVIEW"
  | "IN_HUMAN_REVIEW"
  | "REVISION_REQUESTED"
  | "APPROVED_FOR_ASSEMBLY"
  | "ASSEMBLING_BUNDLE"
  | "ASSEMBLY_FAILED"
  | "READY_FOR_COURT_SUBMISSION"
  | "SUBMITTED"
  | "ARCHIVED"
  | "CANCELLED";

export type StepStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "WAITING_FOR_HUMAN"
  | "BLOCKED"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED"
  | "CANCELLED";

export interface WorkflowStep {
  id: number;
  workflow_id: number;
  step_key: string;
  step_type: "automated" | "human";
  status: StepStatus;
  ordinal: number;
  depends_on: string[];
  celery_task_id: string | null;
  attempt_count: number;
  progress: number;
  input_artifact_ids: number[];
  output_artifact_ids: number[];
  error: Record<string, any> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LegalDraft {
  id: number;
  organization_id: number;
  case_id: number;
  workflow_id: number;
  source_document_id: number | null;
  status: string;
  title: string;
  editor_format: string;
  content_json: Record<string, any>;
  content_text: string | null;
  html_snapshot: string | null;
  version: number;
  parent_draft_id: number | null;
  created_by: string;
  created_by_user_id: number | null;
  approved_by_user_id: number | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CourtBundleSummary {
  id: number;
  workflow_id: number;
  status: string;
  approved_draft_id: number;
  jurisdiction: string | null;
  max_chunk_bytes: number;
  toc_artifact_id: number | null;
  final_artifact_id: number | null;
  manifest: Record<string, any>;
  error: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEvent {
  id: number;
  organization_id: number;
  case_id: number;
  workflow_id: number;
  step_key: string | null;
  event_type: string;
  actor_type: string;
  actor_user_id: number | null;
  payload: Record<string, any>;
  created_at: string;
}

export interface Workflow {
  id: number;
  organization_id: number;
  case_id: number;
  workflow_type: string;
  status: WorkflowStatus;
  current_step_key: string | null;
  source_document_id: number | null;
  active_draft_id: number | null;
  final_bundle_id: number | null;
  assigned_user_id: number | null;
  created_by_user_id: number;
  metadata: Record<string, any>;
  error: Record<string, any> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  steps: WorkflowStep[];
  drafts: LegalDraft[];
  bundle: CourtBundleSummary | null;
  recent_events: WorkflowEvent[];
}

export interface CreateWorkflowInput {
  case_id: number;
  source_document_id?: number | null;
  workflow_type?: string;
  assigned_user_id?: number | null;
  metadata?: Record<string, any>;
}

// ─── Workflow APIs ────────────────────────────────────────────────────────

export const workflowsApi = {
  async createWorkflow(input: CreateWorkflowInput): Promise<Workflow> {
    const res = await axios.post(`${API_BASE}/api/v1/workflows`, input, {
      headers: authHeaders(),
    });
    return res.data;
  },

  async getWorkflow(workflowId: number): Promise<Workflow> {
    const res = await axios.get(`${API_BASE}/api/v1/workflows/${workflowId}`, {
      headers: authHeaders(),
    });
    return res.data;
  },

  async listCaseWorkflows(caseId: number): Promise<Workflow[]> {
    const res = await axios.get(
      `${API_BASE}/api/v1/cases/${caseId}/workflows`,
      { headers: authHeaders() }
    );
    return res.data;
  },

  async startWorkflow(workflowId: number): Promise<Workflow> {
    const res = await axios.post(
      `${API_BASE}/api/v1/workflows/${workflowId}/start`,
      {},
      { headers: authHeaders() }
    );
    return res.data;
  },

  async cancelWorkflow(workflowId: number): Promise<Workflow> {
    const res = await axios.post(
      `${API_BASE}/api/v1/workflows/${workflowId}/cancel`,
      {},
      { headers: authHeaders() }
    );
    return res.data;
  },

  async retryStep(workflowId: number, stepKey: string): Promise<Workflow> {
    const res = await axios.post(
      `${API_BASE}/api/v1/workflows/${workflowId}/retry-step/${encodeURIComponent(stepKey)}`,
      {},
      { headers: authHeaders() }
    );
    return res.data;
  },

  async getEvents(workflowId: number): Promise<WorkflowEvent[]> {
    const res = await axios.get(
      `${API_BASE}/api/v1/workflows/${workflowId}/events`,
      { headers: authHeaders() }
    );
    return res.data;
  },

  // ─── Draft APIs ──────────────────────────────────────────────────────────

  async listDrafts(workflowId: number): Promise<LegalDraft[]> {
    const res = await axios.get(
      `${API_BASE}/api/v1/workflows/${workflowId}/drafts`,
      { headers: authHeaders() }
    );
    return res.data;
  },

  async updateDraft(
    draftId: number,
    patch: {
      title?: string;
      content_json?: Record<string, any>;
      content_text?: string;
      html_snapshot?: string;
      version?: number;
    }
  ): Promise<LegalDraft> {
    const res = await axios.patch(
      `${API_BASE}/api/v1/drafts/${draftId}`,
      patch,
      { headers: authHeaders() }
    );
    return res.data;
  },

  async approveDraft(draftId: number): Promise<LegalDraft> {
    const res = await axios.post(
      `${API_BASE}/api/v1/drafts/${draftId}/approve`,
      {},
      { headers: authHeaders() }
    );
    return res.data;
  },

  async requestRevision(
    draftId: number,
    instructions?: string
  ): Promise<LegalDraft> {
    const res = await axios.post(
      `${API_BASE}/api/v1/drafts/${draftId}/request-revision`,
      { instructions },
      { headers: authHeaders() }
    );
    return res.data;
  },

  // ─── Bundle APIs ─────────────────────────────────────────────────────────

  async createBundle(
    workflowId: number,
    payload: {
      approved_draft_id: number;
      jurisdiction?: string;
      court_profile?: Record<string, any>;
      max_chunk_bytes?: number;
    }
  ): Promise<CourtBundleSummary> {
    const res = await axios.post(
      `${API_BASE}/api/v1/workflows/${workflowId}/bundle`,
      payload,
      { headers: authHeaders() }
    );
    return res.data;
  },

  async getBundle(bundleId: number): Promise<CourtBundleSummary> {
    const res = await axios.get(`${API_BASE}/api/v1/bundles/${bundleId}`, {
      headers: authHeaders(),
    });
    return res.data;
  },

  async assembleBundle(bundleId: number): Promise<CourtBundleSummary> {
    const res = await axios.post(
      `${API_BASE}/api/v1/bundles/${bundleId}/assemble`,
      {},
      { headers: authHeaders() }
    );
    return res.data;
  },

  async getBundleChunks(bundleId: number): Promise<any[]> {
    const res = await axios.get(
      `${API_BASE}/api/v1/bundles/${bundleId}/chunks`,
      { headers: authHeaders() }
    );
    return res.data;
  },
};

export default workflowsApi;
