
import { OverviewCards } from '../../components/dashboard/OverviewCards';
import { RecentDocs } from '../../components/dashboard/RecentDocs';
import { useAuth } from '../../context/AuthContext';
import { Briefcase, Clock } from 'lucide-react';

export default function Dashboard() {
  const { user } = useAuth();

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  const firstName = user?.name?.split(' ')[0] ?? 'Counselor';

  return (
    <div>
      {/* Personalized header */}
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            {greeting}, {firstName} 👋
          </h1>
          <p className="text-muted-foreground mt-1">
            Here's what's happening in your workspace today.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium bg-slate-100 px-3 py-1.5 rounded-full">
          <Clock className="h-3.5 w-3.5" />
          {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
        </div>
      </div>

      {/* Stats cards */}
      <OverviewCards />

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <RecentDocs />
        </div>
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
            <h3 className="font-serif font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Briefcase className="h-5 w-5 text-primary" />
              Quick Actions
            </h3>
            <div className="space-y-2">
              <a href="/cases" className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors text-sm text-slate-700 font-medium">
                <span className="text-blue-500">📁</span> New Case
              </a>
              <a href="/documents" className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors text-sm text-slate-700 font-medium">
                <span className="text-emerald-500">📄</span> Upload Document
              </a>
              <a href="/email" className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors text-sm text-slate-700 font-medium">
                <span className="text-amber-500">📧</span> Check Email Intake
              </a>
              <a href="/search" className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors text-sm text-slate-700 font-medium">
                <span className="text-purple-500">🔍</span> Search Documents
              </a>
            </div>
          </div>


        </div>
      </div>
    </div>
  );
}
