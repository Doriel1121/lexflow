// src/types.ts

export interface User {
  id: number;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  social_id?: string;
  provider?: string;
  role?: string;
}

export interface Case {
  id: number;
  title: string;
  description?: string;
  status: 'open' | 'closed' | 'pending';
  client_id: number;
  client_name?: string;
  created_by_user_id: number;
  assigned_lawyer_id?: number;
  assigned_lawyer_name?: string;
  priority?: 'critical' | 'high' | 'normal' | 'low';
  priority_score?: number;
  created_at: string;
  updated_at: string;
  notes: CaseNote[];
  documents: Document[]; // Assuming documents are directly part of the case for display
}

export interface CaseNote {
  id: number;
  case_id: number;
  user_id: number;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: number;
  filename: string;
  s3_url: string;
  case_id: number;
  uploaded_by_user_id: number;
  content?: string;
  classification?: string;
  language?: string;
  page_count?: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  tags: Tag[];
}

export interface Tag {
  id: number;
  name: string;
  category?: string;
}

export interface Summary {
  id: number;
  document_id: number;
  content: string;
  key_dates?: string[];
  parties?: string[];
  missing_documents_suggestion?: string;
  created_at: string;
  updated_at: string;
}

export interface Client {
  id: number;
  name: string;
  contact_person?: string;
  contact_email?: string;
  phone_number?: string;
  address?: string;
  created_at: string;
  updated_at: string;
}

export interface Deadline {
  id: number;
  deadline_date: string;
  deadline_type?: string;
  title?: string;
  description?: string;
  confidence_score?: number;
  is_completed: boolean;
  document_id?: number;
  document_name?: string;
  case_id?: number;
  assignee_id?: number;
  organization_id?: number;
  created_at: string;
  updated_at: string;
}

export interface CaseEvent {
  id: number;
  case_id: number;
  user_id?: number;
  event_type: string;
  description?: string;
  metadata_json?: Record<string, any>;
  created_at: string;
}

export interface EmployeeStats {
  user_id: number;
  full_name: string;
  email: string;
  role: string;
  open_cases: number;
  total_assigned_cases: number;
  documents_uploaded: number;
  deadline_compliance_rate: number;
  total_deadlines: number;
  completed_deadlines: number;
  overdue_deadlines: number;
  last_activity: string | null;
  cases_created_this_month: number;
}

export interface OrgSummary {
  total_cases: number;
  open_cases: number;
  pending_cases: number;
  closed_cases: number;
  unassigned_cases: number;
  total_documents: number;
  overdue_deadlines: number;
  upcoming_deadlines_7d: number;
  deadline_compliance_rate: number;
  upload_trend: { date: string; count: number }[];
  classification_breakdown: Record<string, number>;
}

export interface WorkloadEntry {
  user_id: number;
  full_name: string;
  case_count: number;
}

export interface DeadlineHealth {
  overdue: number;
  approaching: number;
  on_track: number;
  completed: number;
  compliance_trend: {
    week_start: string;
    total: number;
    completed: number;
    rate: number;
  }[];
}

export interface Citation {
  document_id: number;
  page?: number;
}

export interface AskAIRequest {
  question: string;
  case_id?: number;
  document_ids?: number[];
  top_k?: number;
}

export interface AskAIResponse {
  answer: string;
  citations: Citation[];
}

export interface GlobalSearchResult {
  documents: Document[];
  cases: Case[];
  clients: Client[];
}

export interface Token {
  access_token: string;
  token_type: string;
}
