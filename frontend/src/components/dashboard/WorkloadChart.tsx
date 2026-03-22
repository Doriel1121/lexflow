import { useState, useEffect } from 'react';
import { BarChart3 } from 'lucide-react';
import api from '../../services/api';
import type { WorkloadEntry } from '../../types';

export function WorkloadChart() {
  const [data, setData] = useState<WorkloadEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchWorkload(); }, []);

  const fetchWorkload = async () => {
    try {
      const res = await api.get('/v1/org/analytics/workload');
      setData(res.data);
    } catch { /* silent */ } finally { setLoading(false); }
  };

  const maxCount = Math.max(...data.map(d => d.case_count), 1);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl p-5 animate-pulse">
        <div className="h-5 bg-slate-100 rounded w-1/3 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="h-6 bg-slate-50 rounded" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="h-4 w-4 text-slate-500" />
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">Workload Distribution</h3>
      </div>

      {data.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No data available</p>
      ) : (
        <div className="space-y-3">
          {data.map(entry => (
            <div key={entry.user_id} className="group">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-600 truncate max-w-[60%]">
                  {entry.full_name}
                </span>
                <span className="text-xs font-bold text-slate-500">
                  {entry.case_count} {entry.case_count === 1 ? 'case' : 'cases'}
                </span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out bg-gradient-to-r from-blue-400 to-indigo-500 group-hover:from-blue-500 group-hover:to-indigo-600"
                  style={{ width: `${(entry.case_count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
