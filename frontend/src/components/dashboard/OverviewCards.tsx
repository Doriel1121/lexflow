import { useEffect, useState } from 'react';
import { Briefcase, FileText, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils';
import api from '../../services/api';

export function OverviewCards() {
  const [stats, setStats] = useState({
    active_cases: 0,
    total_documents: 0,
    action_required: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await api.get('/v1/cases/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const cards = [
    {
      label: "Active Cases",
      value: loading ? "..." : stats.active_cases.toString(),
      icon: Briefcase,
      color: "text-blue-500",
      bg: "bg-blue-50",
    },
    {
      label: "Documents Processed",
      value: loading ? "..." : stats.total_documents.toString(),
      icon: FileText,
      color: "text-emerald-500",
      bg: "bg-emerald-50",
    },
    {
      label: "Action Required",
      value: loading ? "..." : stats.action_required.toString(),
      icon: AlertCircle,
      color: "text-amber-500",
      bg: "bg-amber-50",
    },
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      {cards.map((card, index) => (
        <div key={index} className="bg-card border border-border rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <div className={cn("p-2 rounded-lg", card.bg)}>
              <card.icon className={cn("h-6 w-6", card.color)} />
            </div>
            {index === 2 && (
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse"></span>
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">{card.label}</p>
            <h3 className="text-2xl font-bold text-slate-800 mt-1">{card.value}</h3>
          </div>
        </div>
      ))}
    </div>
  );
}
