/**
 * services/adminService.ts
 * ========================
 * Typed API service for the System Admin dashboard.
 *
 * All types mirror the backend schemas/admin.py (v2).
 * No type here contains org names, org IDs, user emails, or
 * any per-tenant identifiable data.
 */

import api from './api';

// ─── Types ────────────────────────────────────────────────────────────────

export interface TenantStats {
  total_tenants: number;
  active_tenants: number;
  inactive_tenants: number;
  new_tenants_today: number;
  new_tenants_this_month: number;
}

export interface UserStats {
  total_users: number;
  active_users_today: number;
  new_users_today: number;
  avg_users_per_tenant: number;
  users_by_role: Record<string, number>;
}

export interface ContentStats {
  total_documents: number;
  new_documents_today: number;
  total_cases: number;
  new_cases_today: number;
}

export interface ActivityStats {
  ai_calls_today: number;
  api_requests_today: number;
  api_errors_today: number;
  error_rate_pct: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
}

export interface SystemHealthStatus {
  status: 'healthy' | 'degraded' | 'critical' | 'unknown';
  error_rate_pct: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  last_computed: string | null;
}

export interface DailyMetricPoint {
  date: string;   // "YYYY-MM-DD"
  value: number;
}

export interface GrowthPoint {
  month: string;  // "YYYY-MM"
  new_tenants: number;
  churned_tenants: number;
  active_tenants: number;
}

export interface FeatureUsagePoint {
  feature: string;
  call_count: number;
}

export interface AdminDashboardData {
  computed_at: string;
  tenant_stats: TenantStats;
  user_stats: UserStats;
  content_stats: ContentStats;
  activity_stats: ActivityStats;
  system_health: SystemHealthStatus;
  daily_api_calls: DailyMetricPoint[];
  daily_new_tenants: DailyMetricPoint[];
  daily_error_rates: DailyMetricPoint[];
  growth_cohorts: GrowthPoint[];
  feature_usage: FeatureUsagePoint[];
}

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  user_hash: string;
  event_type: string;
  resource_type: string | null;
  http_method: string | null;
  path: string | null;
  status_code: number | null;
  ip_address: string | null;
}

export interface AuditLogsResponse {
  total: number;
  page: number;
  page_size: number;
  logs: AuditLogEntry[];
}

export interface ProvisionRequest {
  organization_name: string;
  admin_email: string;
  admin_name: string;
  password?: string;
}

// ─── API calls ────────────────────────────────────────────────────────────

export const adminService = {
  getDashboard: (): Promise<AdminDashboardData> =>
    api.get('/v1/admin/dashboard').then(r => r.data),

  getGrowth: (months = 12): Promise<{ cohorts: GrowthPoint[] }> =>
    api.get('/v1/admin/growth', { params: { months } }).then(r => r.data),

  getFeatureUsage: (days = 7): Promise<{ period_days: number; items: FeatureUsagePoint[] }> =>
    api.get('/v1/admin/feature-usage', { params: { days } }).then(r => r.data),

  getSystemHealth: (): Promise<SystemHealthStatus> =>
    api.get('/v1/admin/system-health').then(r => r.data),

  getAuditLogs: (
    page = 1,
    pageSize = 50,
    eventType?: string,
  ): Promise<AuditLogsResponse> =>
    api.get('/v1/admin/audit-logs', {
      params: { page, page_size: pageSize, ...(eventType ? { event_type: eventType } : {}) },
    }).then(r => r.data),

  provisionOrganization: (body: ProvisionRequest): Promise<unknown> =>
    api.post('/v1/admin/organizations', body).then(r => r.data),
};
