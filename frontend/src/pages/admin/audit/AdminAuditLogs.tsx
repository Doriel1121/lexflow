import React, { useEffect, useState } from 'react';
import { Activity, Search, Filter } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '../../../services/api';

interface AuditLog {
  id: number;
  timestamp: string;
  user_id: number | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  details: string | null;
  ip_address: string | null;
}

export default function AdminAuditLogs() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  // Infinite Scroll State
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [fetchingMore, setFetchingMore] = useState(false);
  const limit = 50;
  const observerTarget = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchLogs(0);
  }, []);

  const fetchLogs = async (targetPage: number = 0) => {
    try {
      const skip = targetPage * limit;
      if (targetPage === 0) setLoading(true);
      else setFetchingMore(true);

      const res = await api.get('/v1/admin/audit-logs', { params: { skip, limit } });
      const incomingLogs = res.data;

      if (targetPage === 0) {
        setLogs(incomingLogs);
      } else {
        setLogs(prev => [...prev, ...incomingLogs]);
      }
      
      setHasMore(incomingLogs.length === limit);
      setPage(targetPage);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
      setFetchingMore(false);
    }
  };

  // Intersection Observer for Infinite Scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasMore && !loading && !fetchingMore && !searchTerm) {
          // If searching locally (not calling API for search), infinite scroll appending is mostly paused or should only load next page
          fetchLogs(page + 1);
        }
      },
      { threshold: 1.0 }
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasMore, loading, fetchingMore, page, searchTerm]);

  const filteredLogs = logs.filter(log => 
    (log.action || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
    (log.entity_type || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.details || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">{t('adminAudit.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('adminAudit.subtitle')}</p>
        </div>
        <button className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg font-medium transition-colors border border-slate-200">
          <Filter className="h-4 w-4" />
          {t('adminAudit.filterLogs')}
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col flex-1">
        <div className="p-4 border-b border-slate-200 shrink-0">
          <div className="relative max-w-sm">
            <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder={t('adminAudit.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full ps-9 pe-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-y-auto flex-1">
          <table className="w-full text-sm text-start">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-6 py-3">{t('adminAudit.table.timestamp')}</th>
                <th className="px-6 py-3">{t('adminAudit.table.userId')}</th>
                <th className="px-6 py-3">{t('adminAudit.table.action')}</th>
                <th className="px-6 py-3">{t('adminAudit.table.entity')}</th>
                <th className="px-6 py-3">{t('adminAudit.table.details')}</th>
                <th className="px-6 py-3">{t('adminAudit.table.ipAddress')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && page === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin mb-4" />
                      {t('adminAudit.loading')}
                    </div>
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    {t('adminAudit.noLogs')}
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-3 whitespace-nowrap text-slate-500 font-mono text-xs">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-3">
                      {log.user_id ? (
                        <span className="font-mono text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                          UID-{log.user_id}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic text-xs">{t('adminAudit.system')}</span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-2 font-medium text-slate-700">
                        <Activity className="h-3.5 w-3.5 text-slate-400" />
                        {log.action}
                      </div>
                    </td>
                    <td className="px-6 py-3">
                      {log.entity_type ? (
                        <span className="flex items-center gap-1.5 text-xs text-slate-600">
                          <span className="font-semibold">{log.entity_type}</span>
                          {log.entity_id && <span className="text-slate-400">#{log.entity_id}</span>}
                        </span>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-slate-600 text-xs">
                      {log.details || <span className="text-slate-300">-</span>}
                    </td>
                    <td className="px-6 py-3 whitespace-nowrap text-slate-500 font-mono text-xs">
                      {log.ip_address || t('adminAudit.unknown')}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Infinite Scroll Sentinel */}
          {!loading && !searchTerm && (
            <div ref={observerTarget} className="py-4 text-center mt-2">
              {fetchingMore && <span className="text-sm text-slate-500 animate-pulse">{t('adminAudit.loadingMore')}</span>}
              {!hasMore && logs.length > 0 && <span className="text-xs text-slate-400">{t('adminAudit.endOfRecords')}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
