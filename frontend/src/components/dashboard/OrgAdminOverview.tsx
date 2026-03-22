import { useState, useEffect } from 'react';
import { Briefcase, FileText, AlertTriangle, Users, Clock, CheckCircle } from 'lucide-react';
import api from '../../services/api';
import type { OrgSummary } from '../../types';

export function OrgAdminOverview() {
  const [summary, setSummary] = useState<OrgSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchSummary(); }, []);

  const fetchSummary = async () => {
    try {
      const res = await api.get('/v1/org/analytics/summary');
      setSummary(res.data);
    } catch { /* silent */ } finally { setLoading(false); }
  };

  if (loading || !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 animate-pulse">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="bg-white rounded-2xl p-4 h-24" />
        ))}
      </div>
    );
  }

  const cards = [
    { label: 'Open Cases', value: summary.open_cases, icon: Briefcase, color: 'text-blue-600 bg-blue-50' },
    { label: 'Documents', value: summary.total_documents, icon: FileText, color: 'text-emerald-600 bg-emerald-50' },
    { label: 'Overdue', value: summary.overdue_deadlines, icon: AlertTriangle, color: summary.overdue_deadlines > 0 ? 'text-red-600 bg-red-50' : 'text-slate-400 bg-slate-50' },
    { label: 'Due in 7 Days', value: summary.upcoming_deadlines_7d, icon: Clock, color: 'text-amber-600 bg-amber-50' },
    { label: 'Unassigned', value: summary.unassigned_cases, icon: Users, color: summary.unassigned_cases > 0 ? 'text-orange-600 bg-orange-50' : 'text-slate-400 bg-slate-50' },
    { label: 'Compliance', value: `${summary.deadline_compliance_rate}%`, icon: CheckCircle, color: summary.deadline_compliance_rate >= 80 ? 'text-emerald-600 bg-emerald-50' : 'text-amber-600 bg-amber-50' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map(card => (
        <div
          key={card.label}
          className="bg-white rounded-2xl p-4 hover:shadow-md transition-shadow duration-200"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{card.label}</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{card.value}</p>
            </div>
            <div className={`p-1.5 rounded-lg ${card.color}`}>
              <card.icon className="h-4 w-4" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
