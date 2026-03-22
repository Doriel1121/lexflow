import { useState, useEffect } from 'react';
import { AlertTriangle, Clock, CheckCircle2, Shield } from 'lucide-react';
import api from '../../services/api';
import type { DeadlineHealth } from '../../types';

export function DeadlineHealthWidget() {
  const [health, setHealth] = useState<DeadlineHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchHealth(); }, []);

  const fetchHealth = async () => {
    try {
      const res = await api.get('/v1/org/analytics/deadlines');
      setHealth(res.data);
    } catch { /* silent */ } finally { setLoading(false); }
  };

  if (loading || !health) {
    return (
      <div className="bg-white rounded-2xl p-5 animate-pulse">
        <div className="h-5 bg-slate-100 rounded w-1/2 mb-4" />
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map(i => <div key={i} className="h-16 bg-slate-50 rounded-xl" />)}
        </div>
      </div>
    );
  }

  const cards = [
    {
      label: 'Overdue',
      value: health.overdue,
      icon: AlertTriangle,
      bg: 'bg-red-50',
      text: 'text-red-600',
      ring: health.overdue > 0 ? 'ring-2 ring-red-200' : '',
    },
    {
      label: 'Due in 7d',
      value: health.approaching,
      icon: Clock,
      bg: 'bg-amber-50',
      text: 'text-amber-600',
      ring: '',
    },
    {
      label: 'On Track',
      value: health.on_track,
      icon: CheckCircle2,
      bg: 'bg-emerald-50',
      text: 'text-emerald-600',
      ring: '',
    },
  ];

  return (
    <div className="bg-white rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="h-4 w-4 text-slate-500" />
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">Deadline Health</h3>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        {cards.map(card => (
          <div key={card.label} className={`rounded-xl p-3 text-center ${card.bg} ${card.ring} transition-shadow`}>
            <card.icon className={`h-4 w-4 mx-auto mb-1 ${card.text}`} />
            <p className={`text-2xl font-bold ${card.text}`}>{card.value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Compliance trend sparkline */}
      {health.compliance_trend.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-2">Weekly compliance trend</p>
          <div className="flex items-end gap-1 h-10">
            {health.compliance_trend.map((week, i) => (
              <div
                key={i}
                className="flex-1 rounded-t transition-all duration-300 hover:opacity-80"
                style={{
                  height: `${Math.max(week.rate, 5)}%`,
                  backgroundColor: week.rate >= 80 ? '#10b981' : week.rate >= 50 ? '#f59e0b' : '#ef4444',
                }}
                title={`${week.week_start}: ${week.rate}% compliance`}
              />
            ))}
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-slate-300">4 weeks ago</span>
            <span className="text-[10px] text-slate-300">This week</span>
          </div>
        </div>
      )}
    </div>
  );
}
