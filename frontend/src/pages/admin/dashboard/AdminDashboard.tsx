import { useEffect, useState } from 'react';
import { Users, Building2, Database, Briefcase } from 'lucide-react';
import api from '../../../services/api';
import { cn } from '../../../lib/utils';

interface AdminStats {
  summary: {
    total_users: number;
    total_orgs: number;
    total_documents: number;
    total_cases: number;
    avg_org_size: number;
    active_subscriptions: number;
  };
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const res = await api.get('/v1/admin/dashboard');
      setStats(res.data);
    } catch (err: any) {
      console.error('Failed to load admin stats', err);
      setError('Failed to load system statistics.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-500 font-medium">Loading system metrics...</div>;
  }

  if (error || !stats) {
    return (
      <div className="p-8 text-center text-red-500 font-medium">
        {error || 'An error occurred loading the dashboard.'}
      </div>
    );
  }

  const { summary } = stats;

  const cards = [
    {
      label: "Total Organizations",
      value: summary.total_orgs.toString(),
      subtext: `${summary.active_subscriptions} active subscriptions`,
      icon: Building2,
      color: "text-blue-600",
      bg: "bg-blue-100",
    },
    {
      label: "Total Platform Users",
      value: summary.total_users.toString(),
      subtext: `Avg ${summary.avg_org_size} users / org`,
      icon: Users,
      color: "text-indigo-600",
      bg: "bg-indigo-100",
    },
    {
      label: "Documents Processed",
      value: summary.total_documents.toString(),
      subtext: "System-wide volume",
      icon: Database,
      color: "text-emerald-600",
      bg: "bg-emerald-100",
    },
    {
      label: "Total Cases",
      value: summary.total_cases.toString(),
      subtext: "System-wide volume",
      icon: Briefcase,
      color: "text-purple-600",
      bg: "bg-purple-100",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">System Overview</h1>
        <p className="text-muted-foreground mt-1">Platform-wide analytics and health metrics.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {cards.map((card, idx) => (
          <div key={idx} className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className={cn("p-2.5 rounded-lg", card.bg)}>
                <card.icon className={cn("h-6 w-6", card.color)} />
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">{card.label}</p>
              <h3 className="text-3xl font-bold text-slate-800 mt-1">{card.value}</h3>
              <p className="text-xs text-slate-400 mt-1.5 font-medium">{card.subtext}</p>
            </div>
          </div>
        ))}
      </div>


    </div>
  );
}
