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
  created_by_user_id: number;
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

export interface Token {
  access_token: string;
  token_type: string;
}
