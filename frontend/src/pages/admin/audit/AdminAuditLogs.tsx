import React, { useEffect, useState, useCallback } from 'react';
import { Activity, Search, Filter, ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService, AuditLogEntry } from '../../../services/adminService';
import { cn } from '../../../lib/utils';

export default function AdminAuditLogs() {
  const { t } = useTranslation();

  const [logs, setLogs]               = useState<AuditLogEntry[]>([]);
  const [total, setTotal]             = useState(0);
  const [page, setPage]               = useState(1);
  const [hasMore, setHasMore]         = useState(true);
  const [loading, setLoading]         = useState(true);
  const [fetchingMore, setFetchingMore] = useState(false);
  const [searchTerm, setSearchTerm]   = useState('');
  const [eventFilter, setEventFilter] = useState('');

  const PAGE_SIZE = 50;
  const observerTarget = React.useRef<HTMLDivElement>(null);

  // ── Initial load ──────────────────────────────────────────────────────
  const loadPage = useCallback(async (targetPage: number, reset = false) => {
    try {
      if (targetPage === 1) setLoading(true);
      else setFetchingMore(true);

      const res = await adminService.getAuditLogs(
        targetPage,
        PAGE_SIZE,
        eventFilter || undefined,
      );

      // res.logs is guaranteed to be an array by adminService types
      const incoming: AuditLogEntry[] = Array.isArray(res.logs) ? res.logs : [];

      setTotal(res.total ?? 0);
      setLogs(prev => (reset || targetPage === 1) ? incoming : [...prev, ...incoming]);
      setHasMore(incoming.length === PAGE_SIZE);
      setPage(targetPage);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
      setFetchingMore(false);
    }
  }, [eventFilter]);

  useEffect(() => { loadPage(1, true); }, [loadPage]);

  // ── Infinite scroll ───────────────────────────────────────────────────
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore && !loading && !fetchingMore && !searchTerm) {
        loadPage(page + 1);
      }
    }, { threshold: 1.0 });

    if (observerTarget.current) observer.observe(observerTarget.current);
    return () => observer.disconnect();
  }, [hasMore, loading, fetchingMore, page, searchTerm, loadPage]);

  // ── Client-side search filter (on already-loaded logs) ───────────────
  const filteredLogs = logs.filter(log => {
    if (!searchTerm) return true;
    const q = searchTerm.toLowerCase();
    return (
      (log.event_type  ?? '').toLowerCase().includes(q) ||
      (log.resource_type ?? '').toLowerCase().includes(q) ||
      (log.path        ?? '').toLowerCase().includes(q) ||
      (log.user_hash   ?? '').toLowerCase().includes(q) ||
      (log.ip_address  ?? '').toLowerCase().includes(q)
    );
  });

  // ── Method badge color ────────────────────────────────────────────────
  const methodColor = (m: string | null) => {
    switch (m) {
      case 'GET':    return 'bg-sky-100 text-sky-700';
      case 'POST':   return 'bg-emerald-100 text-emerald-700';
      case 'PUT':
      case 'PATCH':  return 'bg-amber-100 text-amber-700';
      case 'DELETE': return 'bg-red-100 text-red-700';
      default:       return 'bg-slate-100 text-slate-600';
    }
  };

  const statusColor = (code: number | null) => {
    if (!code) return 'text-slate-400';
    if (code < 300) return 'text-emerald-600';
    if (code < 400) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-4rem)]">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            {t('adminAudit.title', { defaultValue: 'Audit Logs' })}
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            {t('adminAudit.subtitle', { defaultValue: 'Anonymized system-wide activity log' })}
            {total > 0 && (
              <span className="ml-2 text-slate-400">· {total.toLocaleString()} total records</span>
            )}
          </p>
        </div>

        {/* Event type filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={eventFilter}
            onChange={e => { setEventFilter(e.target.value); }}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
          >
            <option value="">All events</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT / PATCH</option>
            <option value="DELETE">DELETE</option>
          </select>
        </div>
      </div>

      {/* Privacy notice */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg shrink-0">
        <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0" />
        <p className="text-xs text-amber-700 font-medium">
          User IDs are replaced with 12-character SHA-256 hashes. No personal data is exposed in this view.
        </p>
      </div>

      {/* Table card */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col flex-1">

        {/* Search bar */}
        <div className="p-4 border-b border-slate-200 shrink-0">
          <div className="relative max-w-sm">
            <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search events, paths, user hashes…"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full ps-9 pe-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-y-auto flex-1">
          <table className="w-full text-sm text-start">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-5 py-3 text-start">Timestamp</th>
                <th className="px-5 py-3 text-start">User (hashed)</th>
                <th className="px-5 py-3 text-start">Event</th>
                <th className="px-5 py-3 text-start">Method</th>
                <th className="px-5 py-3 text-start">Path</th>
                <th className="px-5 py-3 text-start">Status</th>
                <th className="px-5 py-3 text-start">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">

              {/* Loading state */}
              {loading && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center gap-3">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin" />
                      Loading audit logs…
                    </div>
                  </td>
                </tr>
              )}

              {/* Empty state */}
              {!loading && filteredLogs.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                    {searchTerm ? 'No logs match your search.' : 'No audit events recorded yet.'}
                  </td>
                </tr>
              )}

              {/* Log rows */}
              {!loading && filteredLogs.map(log => (
                <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3 whitespace-nowrap text-slate-500 font-mono text-xs tabular-nums">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <span className="font-mono text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                      {log.user_hash}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1.5 font-medium text-slate-700 text-xs">
                      <Activity className="h-3 w-3 text-slate-400 shrink-0" />
                      <span className="truncate max-w-[180px]">{log.event_type}</span>
                    </div>
                    {log.resource_type && (
                      <span className="text-[10px] text-slate-400 ms-[18px]">{log.resource_type}</span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    {log.http_method ? (
                      <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded uppercase', methodColor(log.http_method))}>
                        {log.http_method}
                      </span>
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-slate-500 max-w-[200px]">
                    <span className="truncate block" title={log.path ?? ''}>
                      {log.path ?? '—'}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className={cn('text-xs font-semibold tabular-nums', statusColor(log.status_code))}>
                      {log.status_code ?? '—'}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {log.ip_address ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Infinite scroll sentinel */}
          {!loading && !searchTerm && (
            <div ref={observerTarget} className="py-4 text-center">
              {fetchingMore && (
                <span className="text-sm text-slate-400 animate-pulse">Loading more…</span>
              )}
              {!hasMore && logs.length > 0 && (
                <span className="text-xs text-slate-300">End of records</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
