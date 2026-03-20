/**
 * AdminDashboard.tsx  —  REDESIGNED (v2)
 * ========================================
 * System Admin dashboard — strictly system-level aggregated metrics.
 *
 * What this component shows:
 *   ✅ KPI cards: tenant counts, user counts, content volume, activity
 *   ✅ System health indicator
 *   ✅ 30-day API call volume chart
 *   ✅ 30-day error rate chart
 *   ✅ 12-month tenant growth chart
 *   ✅ Feature usage bar chart (last 7 days)
 *   ✅ Role distribution (anonymous counts)
 *
 * What this component NEVER shows:
 *   ❌ Org names, org IDs, org slugs
 *   ❌ User emails, user names, user IDs
 *   ❌ Per-tenant document/case counts
 *   ❌ Any table of raw tenant or user records
 */

import { useEffect, useState, useCallback } from 'react';
import {
  Building2, Users, FileText, Briefcase,
  Activity, Zap, AlertTriangle, CheckCircle2,
  TrendingUp, RefreshCw, Clock, AlertCircle,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { adminService, AdminDashboardData } from '../../../services/adminService';
import { cn } from '../../../lib/utils';

// ─── Sub-components ────────────────────────────────────────────────────────

interface KPICardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  trend?: { value: number; label: string };
}

function KPICard({ label, value, subtext, icon: Icon, iconColor, iconBg, trend }: KPICardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className={cn('p-2.5 rounded-lg', iconBg)}>
          <Icon className={cn('h-5 w-5', iconColor)} />
        </div>
        {trend && (
          <span className={cn(
            'text-xs font-semibold px-2 py-0.5 rounded-full',
            trend.value >= 0
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-red-50 text-red-600',
          )}>
            {trend.value >= 0 ? '+' : ''}{trend.value} {trend.label}
          </span>
        )}
      </div>
      <p className="text-sm font-medium text-slate-500 mb-1">{label}</p>
      <h3 className="text-3xl font-bold text-slate-800 tabular-nums">{value}</h3>
      {subtext && <p className="text-xs text-slate-400 mt-1.5 font-medium">{subtext}</p>}
    </div>
  );
}

function HealthBadge({ status }: { status: string }) {
  const map = {
    healthy:  { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', icon: CheckCircle2, label: 'Healthy' },
    degraded: { bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500',   icon: AlertTriangle, label: 'Degraded' },
    critical: { bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500',     icon: AlertCircle,  label: 'Critical' },
    unknown:  { bg: 'bg-slate-100',   text: 'text-slate-500',   dot: 'bg-slate-400',   icon: Clock,        label: 'Unknown' },
  };
  const cfg = map[status as keyof typeof map] ?? map.unknown;
  const Icon = cfg.icon;
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold', cfg.bg, cfg.text)}>
      <Icon className="h-4 w-4" />
      {cfg.label}
    </span>
  );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
  );
}

const CHART_COLORS = {
  primary:  '#7c3aed',
  secondary:'#3b82f6',
  success:  '#10b981',
  warning:  '#f59e0b',
  error:    '#ef4444',
  muted:    '#94a3b8',
};

// Friendly feature name mapping
const FEATURE_LABELS: Record<string, string> = {
  ai_chat:          'AI Chat',
  document_upload:  'Doc Upload',
  risk_analysis:    'Risk Analysis',
  deadline_tracker: 'Deadlines',
  case_management:  'Cases',
  email_ingest:     'Email Ingest',
  search:           'Search',
};

const formatFeature = (key: string) =>
  FEATURE_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// ─── Main Component ────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await adminService.getDashboard();
      setData(result);
      setLastRefreshed(new Date());
    } catch (err: any) {
      console.error('AdminDashboard load error:', err);
      setError(err?.response?.data?.detail ?? 'Failed to load system metrics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin" />
          <p className="text-slate-500 text-sm font-medium">Loading system metrics…</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center space-y-3">
          <AlertCircle className="h-10 w-10 text-red-400 mx-auto" />
          <p className="text-red-600 font-medium">{error ?? 'Unknown error'}</p>
          <button
            onClick={load}
            className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { tenant_stats, user_stats, content_stats, activity_stats, system_health } = data;

  // Chart data
  const apiCallsData = data.daily_api_calls.map(p => ({
    date: p.date.slice(5),  // "MM-DD"
    calls: p.value,
  }));

  const errorRateData = data.daily_error_rates.map(p => ({
    date: p.date.slice(5),
    rate: p.value,
  }));

  const growthData = data.growth_cohorts.map(c => ({
    month: c.month.slice(0, 7),  // "YYYY-MM"
    new: c.new_tenants,
    active: c.active_tenants,
    churned: c.churned_tenants,
  }));

  const featureData = data.feature_usage.map(f => ({
    name: formatFeature(f.feature),
    calls: f.call_count,
  }));

  const roleData = Object.entries(user_stats.users_by_role).map(([role, count]) => ({
    name: role.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()),
    count,
  }));

  return (
    <div className="space-y-8">

      {/* ── Page header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            System Overview
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Platform-wide aggregated metrics · No tenant-identifiable data
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Health:</span>
            <HealthBadge status={system_health.status} />
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {lastRefreshed && (
        <p className="text-xs text-slate-400 -mt-5 flex items-center gap-1">
          <Clock className="h-3 w-3" />
          Last updated: {lastRefreshed.toLocaleTimeString()}
        </p>
      )}

      {/* ── KPI cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Tenants"
          value={tenant_stats.total_tenants.toLocaleString()}
          subtext={`${tenant_stats.active_tenants} active · ${tenant_stats.inactive_tenants} inactive`}
          icon={Building2}
          iconColor="text-purple-600"
          iconBg="bg-purple-100"
          trend={{ value: tenant_stats.new_tenants_today, label: 'today' }}
        />
        <KPICard
          label="Platform Users"
          value={user_stats.total_users.toLocaleString()}
          subtext={`Avg ${user_stats.avg_users_per_tenant} users/tenant`}
          icon={Users}
          iconColor="text-blue-600"
          iconBg="bg-blue-100"
          trend={{ value: user_stats.new_users_today, label: 'today' }}
        />
        <KPICard
          label="Documents Processed"
          value={content_stats.total_documents.toLocaleString()}
          subtext={`${content_stats.new_documents_today} uploaded today`}
          icon={FileText}
          iconColor="text-emerald-600"
          iconBg="bg-emerald-100"
        />
        <KPICard
          label="Active Cases"
          value={content_stats.total_cases.toLocaleString()}
          subtext={`${content_stats.new_cases_today} opened today`}
          icon={Briefcase}
          iconColor="text-amber-600"
          iconBg="bg-amber-100"
        />
      </div>

      {/* ── System health row ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="AI Calls Today"
          value={activity_stats.ai_calls_today.toLocaleString()}
          subtext="System-wide AI usage"
          icon={Zap}
          iconColor="text-violet-600"
          iconBg="bg-violet-100"
        />
        <KPICard
          label="API Requests Today"
          value={activity_stats.api_requests_today.toLocaleString()}
          subtext={`${activity_stats.api_errors_today} errors`}
          icon={Activity}
          iconColor="text-sky-600"
          iconBg="bg-sky-100"
        />
        <KPICard
          label="Error Rate"
          value={`${activity_stats.error_rate_pct.toFixed(1)}%`}
          subtext={activity_stats.error_rate_pct > 3 ? '⚠ Above threshold' : 'Within normal range'}
          icon={AlertTriangle}
          iconColor={activity_stats.error_rate_pct > 3 ? 'text-red-600' : 'text-slate-400'}
          iconBg={activity_stats.error_rate_pct > 3 ? 'bg-red-100' : 'bg-slate-100'}
        />
        <KPICard
          label="Avg Latency"
          value={`${activity_stats.avg_latency_ms.toFixed(0)} ms`}
          subtext={`P95: ${activity_stats.p95_latency_ms.toFixed(0)} ms`}
          icon={Clock}
          iconColor={activity_stats.avg_latency_ms > 1000 ? 'text-amber-600' : 'text-teal-600'}
          iconBg={activity_stats.avg_latency_ms > 1000 ? 'bg-amber-100' : 'bg-teal-100'}
        />
      </div>

      {/* ── Charts row 1: API volume + Error rate ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <SectionHeader
            title="API Call Volume"
            subtitle="System-wide requests over the last 30 days"
          />
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={apiCallsData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="callsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={CHART_COLORS.primary} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                formatter={(v: number) => [v.toLocaleString(), 'Requests']}
              />
              <Area
                type="monotone"
                dataKey="calls"
                stroke={CHART_COLORS.primary}
                strokeWidth={2}
                fill="url(#callsGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <SectionHeader
            title="Error Rate"
            subtitle="Percentage of failed requests over 30 days"
          />
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={errorRateData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="errorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={CHART_COLORS.error} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={CHART_COLORS.error} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                formatter={(v: number) => [`${v.toFixed(2)}%`, 'Error Rate']}
              />
              <Area
                type="monotone"
                dataKey="rate"
                stroke={CHART_COLORS.error}
                strokeWidth={2}
                fill="url(#errorGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Charts row 2: Growth + Feature usage ──────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <SectionHeader
            title="Tenant Growth"
            subtitle="New and active tenants per month"
          />
          {growthData.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
              Not enough data yet · check back after the first month
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={growthData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: '#64748b' }} />
                <Bar dataKey="new"    name="New"    fill={CHART_COLORS.primary}  radius={[3,3,0,0]} />
                <Bar dataKey="active" name="Active" fill={CHART_COLORS.success}  radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <SectionHeader
            title="Feature Usage"
            subtitle="System-wide feature calls over the last 7 days"
          />
          {featureData.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
              No feature usage data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={featureData}
                layout="vertical"
                margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} width={90} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                  formatter={(v: number) => [v.toLocaleString(), 'Calls']}
                />
                <Bar dataKey="calls" fill={CHART_COLORS.secondary} radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── User role distribution ─────────────────────────────────────── */}
      {roleData.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <SectionHeader
            title="User Role Distribution"
            subtitle="System-wide count of users per role type"
          />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mt-2">
            {roleData.map(({ name, count }) => (
              <div key={name} className="text-center p-4 bg-slate-50 rounded-lg">
                <div className="text-2xl font-bold text-slate-700 tabular-nums">
                  {count.toLocaleString()}
                </div>
                <div className="text-xs text-slate-500 mt-1 font-medium capitalize">{name}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── New tenant this month callout ──────────────────────────────── */}
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-purple-200 text-sm font-medium">New Tenants This Month</p>
            <h3 className="text-4xl font-bold mt-1 tabular-nums">
              {tenant_stats.new_tenants_this_month}
            </h3>
            <p className="text-purple-200 text-sm mt-2">
              {tenant_stats.active_tenants} tenants currently active on the platform
            </p>
          </div>
          <TrendingUp className="h-16 w-16 text-purple-300 opacity-50" />
        </div>
      </div>

    </div>
  );
}
