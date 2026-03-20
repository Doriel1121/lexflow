import { useEffect, useState } from 'react';
import { Activity, Search, ShieldCheck, User } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import { cn } from '../../lib/utils';

interface AuditLog {
  id: number;
  timestamp: string;
  user_id: number | null;
  user_full_name: string | null;
  user_email: string | null;
  event_type: string;
  resource_type: string | null;
  resource_id: string | null;
  http_method: string | null;
  path: string | null;
  status_code: number | null;
  ip_address: string | null;
  previous_hash: string | null;
  hash: string | null;
}

function UserCell({ log }: { log: AuditLog }) {
  if (!log.user_id) {
    return <span className="text-slate-400 italic text-xs">System</span>;
  }

  const name = log.user_full_name?.trim();
  const email = log.user_email?.trim();
  const initials = name
    ? name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : (email ? email[0].toUpperCase() : '?');

  return (
    <div className="flex items-center gap-2">
      {/* Avatar */}
      <div className="h-7 w-7 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-[10px] font-bold shrink-0">
        {initials}
      </div>
      <div className="min-w-0">
        {name ? (
          <>
            <p className="text-sm font-medium text-slate-800 leading-tight truncate">{name}</p>
            {email && <p className="text-[11px] text-slate-400 truncate">{email}</p>}
          </>
        ) : email ? (
          <p className="text-sm text-slate-700 truncate">{email}</p>
        ) : (
          <span className="font-mono text-xs text-slate-400">UID-{log.user_id}</span>
        )}
      </div>
    </div>
  );
}

export default function OrgAuditLogs() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => { fetchLogs(); }, []);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await api.get('/v1/organizations/audit-logs');
      setLogs(Array.isArray(res.data.items) ? res.data.items : []);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(log => {
    const q = searchTerm.toLowerCase();
    return (
      (log.event_type       ?? '').toLowerCase().includes(q) ||
      (log.resource_type    ?? '').toLowerCase().includes(q) ||
      (log.user_full_name   ?? '').toLowerCase().includes(q) ||
      (log.user_email       ?? '').toLowerCase().includes(q)
    );
  });

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

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            {t('auditLogs.title', { defaultValue: 'Audit Logs' })}
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            {t('auditLogs.subtitle', { defaultValue: 'Full activity log for your organization' })}
          </p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col flex-1">
        <div className="p-4 border-b border-slate-200 shrink-0">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name, email, event…"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-y-auto flex-1">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-5 py-3">Timestamp</th>
                <th className="px-5 py-3">User</th>
                <th className="px-5 py-3">Event</th>
                <th className="px-5 py-3">Resource</th>
                <th className="px-5 py-3">Method</th>
                <th className="px-5 py-3">Integrity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center gap-3">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin" />
                      {t('auditLogs.loading', { defaultValue: 'Loading…' })}
                    </div>
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                    {searchTerm ? 'No logs match your search.' : t('auditLogs.noLogs', { defaultValue: 'No activity recorded yet.' })}
                  </td>
                </tr>
              ) : (
                filteredLogs.map(log => (
                  <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                    {/* Timestamp */}
                    <td className="px-5 py-3 whitespace-nowrap text-slate-500 font-mono text-xs tabular-nums">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>

                    {/* User — name + email + avatar */}
                    <td className="px-5 py-3 max-w-[200px]">
                      <UserCell log={log} />
                    </td>

                    {/* Event */}
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1.5 font-medium text-slate-700 text-xs">
                        <Activity className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                        <span className="truncate max-w-[180px]">{log.event_type}</span>
                      </div>
                    </td>

                    {/* Resource */}
                    <td className="px-5 py-3">
                      {log.resource_type ? (
                        <span className="flex items-center gap-1.5 text-xs text-slate-600">
                          <span className="font-semibold px-2 py-0.5 bg-slate-100 rounded">
                            {log.resource_type}
                          </span>
                          {log.resource_id && (
                            <span className="text-slate-400">#{log.resource_id}</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>

                    {/* Method + status */}
                    <td className="px-5 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {log.http_method && (
                          <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded uppercase', methodColor(log.http_method))}>
                            {log.http_method}
                          </span>
                        )}
                        {log.status_code && (
                          <span className={cn(
                            'text-xs font-semibold tabular-nums',
                            log.status_code < 300 ? 'text-emerald-600' :
                            log.status_code < 400 ? 'text-amber-600' : 'text-red-600',
                          )}>
                            {log.status_code}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Tamper-evident hash */}
                    <td className="px-5 py-3">
                      {log.hash ? (
                        <div
                          className="flex items-center gap-1 text-xs text-emerald-600 cursor-help"
                          title={`Hash: ${log.hash}\nPrev: ${log.previous_hash}`}
                        >
                          <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
                          <span className="font-mono truncate w-20">{log.hash.slice(0, 10)}…</span>
                        </div>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
