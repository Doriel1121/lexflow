
import { OverviewCards } from '../../components/dashboard/OverviewCards';
import { OrgAdminOverview } from '../../components/dashboard/OrgAdminOverview';
import { EmployeeTable } from '../../components/dashboard/EmployeeTable';
import { WorkloadChart } from '../../components/dashboard/WorkloadChart';
import { DeadlineHealthWidget } from '../../components/dashboard/DeadlineHealthWidget';
import { RecentDocs } from '../../components/dashboard/RecentDocs';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Briefcase, FileText, Mail, Search, ArrowRight, Zap } from 'lucide-react';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const hour = new Date().getHours();
  const greetingKey = hour < 12 ? 'dashboard.greeting.morning'
    : hour < 18 ? 'dashboard.greeting.afternoon'
    : 'dashboard.greeting.evening';
  const firstName = user?.name?.split(' ')[0] ?? 'Counselor';

  const isOrgAdmin = user?.role === 'org_admin' || user?.role === 'admin';

  const quickActions = [
    { icon: Briefcase, labelKey: 'dashboard.actions.newCase', descKey: 'dashboard.actions.newCaseDesc', path: '/cases/new', color: 'text-blue-600 bg-blue-50' },
    { icon: FileText, labelKey: 'dashboard.actions.uploadDocument', descKey: 'dashboard.actions.uploadDocumentDesc', path: '/documents', color: 'text-emerald-600 bg-emerald-50' },
    { icon: Mail, labelKey: 'dashboard.actions.emailIntake', descKey: 'dashboard.actions.emailIntakeDesc', path: '/email', color: 'text-amber-600 bg-amber-50' },
    { icon: Search, labelKey: 'dashboard.actions.semanticSearch', descKey: 'dashboard.actions.semanticSearchDesc', path: '/search', color: 'text-purple-600 bg-purple-50' },
  ];

  return (
    <div className="space-y-6">
      {/* Hero greeting */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">
            {t(greetingKey)}, {firstName} 👋
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
      </div>

      {/* Stats — org admin gets the enhanced version */}
      {isOrgAdmin ? <OrgAdminOverview /> : <OverviewCards />}

      {/* Org Admin Analytics Section */}
      {isOrgAdmin && (
        <>
          {/* Employee Performance Table — full width */}
          <EmployeeTable />

          {/* Workload + Deadline Health — side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <WorkloadChart />
            <DeadlineHealthWidget />
          </div>
        </>
      )}

      {/* Two-column content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Documents - spans 2 cols */}
        <div className="lg:col-span-2">
          <RecentDocs />
        </div>

        {/* Quick Actions */}
        <div>
          <div className="bg-white rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="h-4 w-4 text-slate-500" />
              <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">{t('dashboard.quickActions')}</h3>
            </div>
            <div className="space-y-2">
              {quickActions.map((action) => (
                <button
                  key={action.path}
                  onClick={() => navigate(action.path)}
                  className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors group text-left"
                >
                  <div className={`p-2 rounded-lg shrink-0 ${action.color}`}>
                    <action.icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-700">{t(action.labelKey)}</p>
                    <p className="text-xs text-slate-400">{t(action.descKey)}</p>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-slate-500 transition-colors shrink-0" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
