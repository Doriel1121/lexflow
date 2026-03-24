/**
 * AdminUsers.tsx  —  REDESIGNED (v2)
 * =====================================
 * Previously: rendered a full user table with email, name, and organization_id.
 * That violates data isolation — a system admin must never see PII or tenant links.
 *
 * Now: shows aggregated, anonymized user statistics only.
 *   ✅ Total users, active today, new today
 *   ✅ Role distribution (counts, no names)
 *   ✅ Recent audit log activity (hashed user IDs)
 *   ❌ No emails, no names, no organization_id
 */

import { useEffect, useState, useCallback } from 'react';
import { Users, UserCheck, UserPlus, Activity, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { adminService, UserStats, AuditLogEntry } from '../../../services/adminService';
import { cn } from '../../../lib/utils';

const ROLE_COLORS: Record<string, string> = {
  'Org Admin':  'bg-indigo-100 text-indigo-700',
  'Lawyer':     'bg-blue-100 text-blue-700',
  'Assistant':  'bg-emerald-100 text-emerald-700',
  'Viewer':     'bg-slate-100 text-slate-600',
};

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: number | string; icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
      <div className={cn('inline-flex p-2.5 rounded-lg mb-3', `${color}/10`)}>
        <Icon className={cn('h-5 w-5', color)} />
      </div>
      <p className="text-sm text-slate-500 font-medium">{label}</p>
      <h3 className="text-3xl font-bold text-slate-800 mt-1 tabular-nums">{value}</h3>
    </div>
  );
}

export default function AdminUsers() {
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [dashData, logsData] = await Promise.all([
        adminService.getDashboard(),
        adminService.getAuditLogs(1, 20),
      ]);
      setUserStats(dashData.user_stats);
      setAuditLogs(logsData.logs);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to load user metrics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-9 w-9 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin" />
      </div>
    );
  }

  if (error || !userStats) {
    return (
      <div className="p-8 text-center text-red-500 font-medium">
        {error ?? 'An error occurred.'}{' '}
        <button onClick={load} className="underline ml-2">Retry</button>
      </div>
    );
  }

  const roleChartData = Object.entries(userStats.users_by_role).map(([role, count]) => ({
    name: role.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()),
    count,
  }));

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            User Analytics
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Aggregated user statistics · No personal data displayed
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Users"        value={userStats.total_users.toLocaleString()}     icon={Users}      color="text-blue-600" />
        <StatCard label="Active Today"        value={userStats.active_users_today.toLocaleString()} icon={UserCheck} color="text-emerald-600" />
        <StatCard label="New Today"           value={userStats.new_users_today.toLocaleString()}  icon={UserPlus}  color="text-purple-600" />
        <StatCard label="Avg Users / Tenant" value={userStats.avg_users_per_tenant}               icon={Activity}  color="text-amber-600" />
      </div>

      {/* Role distribution chart */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800 mb-1">Role Distribution</h2>
        <p className="text-sm text-slate-500 mb-5">System-wide user count per role type</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          {roleChartData.map(({ name, count }) => (
            <div
              key={name}
              className={cn(
                'text-center p-4 rounded-lg border',
                ROLE_COLORS[name] ?? 'bg-slate-50 text-slate-600 border-slate-200',
              )}
            >
              <div className="text-2xl font-bold tabular-nums">{count.toLocaleString()}</div>
              <div className="text-xs font-medium mt-1 capitalize">{name}</div>
            </div>
          ))}
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={roleChartData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
              formatter={(v: number) => [v.toLocaleString(), 'Users']}
            />
            <Bar dataKey="count" fill="#7c3aed" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent system activity (anonymized) */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">Recent System Activity</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            User IDs are hashed · No personal data is shown
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-100">
              <tr>
                <th className="px-6 py-3 text-start">Timestamp</th>
                <th className="px-6 py-3 text-start">User (hashed)</th>
                <th className="px-6 py-3 text-start">Event</th>
                <th className="px-6 py-3 text-start">Method</th>
                <th className="px-6 py-3 text-start">Path</th>
                <th className="px-6 py-3 text-start">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-slate-400">
                    No audit events recorded yet
                  </td>
                </tr>
              ) : auditLogs.map(log => (
                <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-3 text-slate-500 text-xs tabular-nums whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-3">
                    <span className="font-mono text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                      {log.user_hash}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-slate-700 text-xs font-medium">{log.event_type}</td>
                  <td className="px-6 py-3">
                    {log.http_method && (
                      <span className={cn(
                        'text-[10px] font-bold px-1.5 py-0.5 rounded uppercase',
                        log.http_method === 'GET'    ? 'bg-sky-100 text-sky-700' :
                        log.http_method === 'POST'   ? 'bg-emerald-100 text-emerald-700' :
                        log.http_method === 'DELETE' ? 'bg-red-100 text-red-700' :
                        'bg-amber-100 text-amber-700',
                      )}>
                        {log.http_method}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3 font-mono text-xs text-slate-500 max-w-[200px] truncate">
                    {log.path ?? '—'}
                  </td>
                  <td className="px-6 py-3">
                    {log.status_code && (
                      <span className={cn(
                        'text-xs font-semibold tabular-nums',
                        log.status_code < 300 ? 'text-emerald-600' :
                        log.status_code < 400 ? 'text-amber-600' : 'text-red-600',
                      )}>
                        {log.status_code}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
