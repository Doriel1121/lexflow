import { useEffect, useState } from 'react';
import { Activity, Search, Filter } from 'lucide-react';
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
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await api.get('/v1/admin/audit-logs');
      setLogs(res.data);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(log => 
    (log.action || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
    (log.entity_type || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.details || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Audit Logs</h1>
          <p className="text-muted-foreground mt-1">Platform-wide security and compliance activity feed.</p>
        </div>
        <button className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg font-medium transition-colors border border-slate-200">
          <Filter className="h-4 w-4" />
          Filter Logs
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col flex-1">
        <div className="p-4 border-b border-slate-200 shrink-0">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search actions or entities..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-y-auto flex-1">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-6 py-3">Timestamp</th>
                <th className="px-6 py-3">User ID</th>
                <th className="px-6 py-3">Action</th>
                <th className="px-6 py-3">Entity</th>
                <th className="px-6 py-3">Details</th>
                <th className="px-6 py-3">IP Address</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin mb-4" />
                      Loading system logs...
                    </div>
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    No logs found matching your criteria.
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
                        <span className="text-slate-400 italic text-xs">System</span>
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
                      {log.ip_address || 'Unknown'}
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
