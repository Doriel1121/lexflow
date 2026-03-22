/**
 * services/intakeService.ts
 * ==========================
 * Typed API service for the AI Intake Center.
 */
import api from './api';

export type IntakePriority = 'urgent' | 'high' | 'medium' | 'low';
export type IntakeStatus = 'needs_review' | 'requires_action' | 'auto_processed' | 'completed';

export interface SuggestedCase {
  case_id: number;
  case_title: string;
  reason: string;
  confidence: 'high' | 'medium' | 'low';
}

export interface IntakeItem {
  id: number;
  subject: string;
  from_address: string | null;
  received_at: string | null;
  filename: string;
  classification: string | null;
  ai_insight: string;
  priority: IntakePriority;
  status: IntakeStatus;
  processing_status: string;
  case_id: number | null;
  suggested_case: SuggestedCase | null;
  deadline_count: number;
  nearest_deadline_days: number | null;
}

export interface IntakeSummary {
  total: number;
  needs_review: number;
  requires_action: number;
  auto_processed: number;
  completed: number;
  urgent: number;
}

export interface IntakeListResponse {
  items: IntakeItem[];
  total: number;
  summary: IntakeSummary;
}

export interface DeadlineDetail {
  id: number;
  date: string;
  type: string;
  description: string | null;
  days_until: number;
  confidence: number;
}

export interface EntityDetail {
  name: string;
  role?: string;
  id_number?: string | null;
  contact?: string | null;
  firm?: string | null;
}

export interface IntakeItemDetail extends IntakeItem {
  body_preview: string;
  language: string | null;
  available_lawyers: { id: number; name: string }[];
  ai: {
    summary: string | null;
    classification: string | null;
    entities: EntityDetail[];
    dates: any[];
    amounts: any[];
    case_numbers: string[];
    deadlines: DeadlineDetail[];
  };
}

export interface ConfirmIntakeRequest {
  case_id: number;
  lawyer_id?: number;
  confirm_deadlines?: boolean;
}

export const intakeService = {
  list: (status?: IntakeStatus, offset = 0, limit = 50): Promise<IntakeListResponse> =>
    api.get('/v1/intake', { params: { status, offset, limit } }).then(r => r.data),

  getDetail: (id: number): Promise<IntakeItemDetail> =>
    api.get(`/v1/intake/${id}`).then(r => r.data),

  confirm: (id: number, body: ConfirmIntakeRequest): Promise<unknown> =>
    api.post(`/v1/intake/${id}/confirm`, body).then(r => r.data),

  dismiss: (id: number): Promise<unknown> =>
    api.post(`/v1/intake/${id}/dismiss`).then(r => r.data),
};
