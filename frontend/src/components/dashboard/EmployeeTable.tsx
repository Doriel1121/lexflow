import { useState, useEffect } from 'react';
import { Users, ArrowUpDown, TrendingUp, TrendingDown } from 'lucide-react';
import api from '../../services/api';
import type { EmployeeStats } from '../../types';

type SortKey = 'full_name' | 'open_cases' | 'documents_uploaded' | 'deadline_compliance_rate' | 'overdue_deadlines';

export function EmployeeTable() {
  const [employees, setEmployees] = useState<EmployeeStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('open_cases');
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => { fetchEmployees(); }, []);

  const fetchEmployees = async () => {
    try {
      const res = await api.get('/v1/org/analytics/employees');
      setEmployees(res.data);
    } catch { /* silent */ } finally { setLoading(false); }
  };

  const sorted = [...employees].sort((a, b) => {
    const av = a[sortKey] ?? '';
    const bv = b[sortKey] ?? '';
    if (typeof av === 'number' && typeof bv === 'number') return sortAsc ? av - bv : bv - av;
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const complianceColor = (rate: number) => {
    if (rate >= 80) return 'text-emerald-600 bg-emerald-50';
    if (rate >= 50) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  const SortHeader = ({ label, sortField }: { label: string; sortField: SortKey }) => (
    <th
      className="px-4 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-700 select-none"
      onClick={() => toggleSort(sortField)}
    >
      <span className="flex items-center gap-1">
        {label}
        <ArrowUpDown className="h-3 w-3 opacity-40" />
      </span>
    </th>
  );

  if (loading) {
    return (
      <div className="bg-white rounded-2xl p-6 animate-pulse">
        <div className="h-6 bg-slate-100 rounded w-1/3 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="h-12 bg-slate-50 rounded" />)}
        </div>
      </div>
    );
  }

  if (employees.length === 0) {
    return (
      <div className="bg-white rounded-2xl p-6 text-center text-slate-400">
        <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No team members found</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl overflow-hidden">
      <div className="p-5 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">Team Performance</h3>
          <span className="ml-auto text-xs text-slate-400">{employees.length} members</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50/80">
            <tr>
              <SortHeader label="Name" sortField="full_name" />
              <SortHeader label="Open Cases" sortField="open_cases" />
              <SortHeader label="Docs Uploaded" sortField="documents_uploaded" />
              <SortHeader label="Compliance" sortField="deadline_compliance_rate" />
              <SortHeader label="Overdue" sortField="overdue_deadlines" />
              <th className="px-4 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Last Active</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {sorted.map(emp => (
              <tr key={emp.user_id} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold">
                      {emp.full_name?.charAt(0)?.toUpperCase() || '?'}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-700">{emp.full_name}</p>
                      <p className="text-xs text-slate-400">{emp.role}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-semibold text-slate-700">{emp.open_cases}</span>
                  <span className="text-xs text-slate-400 ml-1">/ {emp.total_assigned_cases}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-semibold text-slate-700">{emp.documents_uploaded}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${complianceColor(emp.deadline_compliance_rate)}`}>
                    {emp.deadline_compliance_rate >= 80
                      ? <TrendingUp className="h-3 w-3" />
                      : <TrendingDown className="h-3 w-3" />
                    }
                    {emp.deadline_compliance_rate}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  {emp.overdue_deadlines > 0 ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold text-red-600 bg-red-50">
                      {emp.overdue_deadlines}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {emp.last_activity
                    ? new Date(emp.last_activity).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                    : 'Never'
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
