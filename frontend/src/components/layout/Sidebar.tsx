import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Inbox, Files, Settings, Scale, Briefcase, LogOut,
  Search, Building2, Users, ClipboardList, FolderGit2,
  ShieldCheck, ChevronDown, ChevronRight, Activity
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';

interface NavGroup {
  labelKey: string;
  items: NavItem[];
  defaultOpen?: boolean;
}

interface NavItem {
  icon: React.ElementType;
  labelKey: string;
  path: string;
  role?: string[];
}

const navGroups: NavGroup[] = [
  {
    labelKey: 'nav.workspace',
    defaultOpen: true,
    items: [
      { icon: LayoutDashboard, labelKey: 'nav.dashboard', path: '/' },
      { icon: Briefcase, labelKey: 'nav.cases', path: '/cases' },
      { icon: Building2, labelKey: 'nav.clients', path: '/clients' },
      { icon: Files, labelKey: 'nav.documents', path: '/documents' },
    ],
  },
  {
    labelKey: 'nav.communication',
    defaultOpen: true,
    items: [
      { icon: Inbox, labelKey: 'nav.emailIntake', path: '/email' },
      { icon: Search, labelKey: 'nav.search', path: '/search' },
      { icon: FolderGit2, labelKey: 'nav.collections', path: '/collections' },
    ],
  },
  {
    labelKey: 'nav.administration',
    defaultOpen: false,
    items: [
      { icon: Users, labelKey: 'nav.team', path: '/team', role: ['ORG_ADMIN', 'ADMIN'] },
      { icon: ShieldCheck, labelKey: 'nav.auditLogs', path: '/settings/audit-logs', role: ['ORG_ADMIN', 'ADMIN'] },
      { icon: Settings, labelKey: 'nav.settings', path: '/settings' },
    ],
  },
];

const adminItems: NavItem[] = [
  { icon: Activity, labelKey: 'nav.systemOverview', path: '/admin' },
  { icon: Building2, labelKey: 'nav.organizations', path: '/admin/organizations' },
  { icon: Users, labelKey: 'nav.usersRoles', path: '/admin/users' },
  { icon: ClipboardList, labelKey: 'nav.auditLogs', path: '/admin/audit-logs' },
];

const roleColors: Record<string, string> = {
  admin: 'bg-purple-500', ADMIN: 'bg-purple-500',
  org_admin: 'bg-indigo-500', ORG_ADMIN: 'bg-indigo-500',
  lawyer: 'bg-blue-500', LAWYER: 'bg-blue-500',
  assistant: 'bg-green-500', ASSISTANT: 'bg-green-500',
  viewer: 'bg-slate-500', VIEWER: 'bg-slate-500',
};

function NavGroupSection({ group, user }: { group: NavGroup; user: any }) {
  const [open, setOpen] = useState(group.defaultOpen ?? true);
  const { t } = useTranslation();

  const visibleItems = group.items.filter(item => {
    if (!item.role) return true;
    const userRole = (user?.role || '').toUpperCase();
    return item.role.map(r => r.toUpperCase()).includes(userRole);
  });

  if (visibleItems.length === 0) return null;

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-300 transition-colors"
      >
        <span>{t(group.labelKey)}</span>
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      </button>
      {open && (
        <div className="space-y-0.5 mt-0.5">
          {visibleItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-sm font-medium',
                  isActive
                    ? 'bg-white/10 text-white'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span>{t(item.labelKey)}</span>
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();
  const [adminOpen, setAdminOpen] = useState(false);
  const isRTL = i18n.language === 'he';

  const isAdmin = user?.role === 'admin' || user?.role === 'ADMIN' || user?.is_superuser;

  const getInitials = (name: string) =>
    name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  const roleLabel = (user?.role as string) === 'ORG_ADMIN'
    ? t('header.orgAdmin')
    : (user?.role ?? 'User');

  return (
    <aside className="h-screen w-60 bg-slate-900 text-white flex flex-col fixed start-0 top-0">
      {/* Logo */}
      <div className="px-4 py-5 flex items-center gap-2.5 border-b border-white/5 shrink-0">
        <div className="bg-primary p-1.5 rounded-lg shrink-0">
          <Scale className="h-5 w-5 text-primary-foreground" />
        </div>
        <span className="font-serif text-lg font-bold tracking-tight">LegalOS</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 overflow-y-auto space-y-3">
        {navGroups.map((group) => (
          <NavGroupSection key={group.labelKey} group={group} user={user} />
        ))}

        {/* Admin section */}
        {isAdmin && (
          <div className="pt-2 border-t border-white/5">
            <button
              onClick={() => setAdminOpen(!adminOpen)}
              className="w-full flex items-center justify-between px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-300 transition-colors"
            >
              <span>{t('nav.backoffice')}</span>
              {adminOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </button>
            {adminOpen && (
              <div className="space-y-0.5 mt-0.5">
                {adminItems.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/admin'}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm font-medium',
                        isActive
                          ? 'bg-purple-600/30 text-purple-300'
                          : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span>{t(item.labelKey)}</span>
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        )}
      </nav>

      {/* User Footer */}
      <div className="p-3 border-t border-white/5 shrink-0">
        {user?.organization && (
          <div className="mb-2 px-2 py-1.5 rounded-lg bg-indigo-500/10">
            <p className="text-xs text-indigo-400 truncate font-medium">{user.organization.name}</p>
          </div>
        )}
        <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-white/5 transition-colors group">
          <div className={cn(
            'h-8 w-8 rounded-full flex items-center justify-center text-white font-bold text-xs shrink-0',
            roleColors[user?.role ?? 'viewer'] ?? 'bg-slate-500'
          )}>
            {user ? getInitials(user.name) : 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate leading-tight">{user?.name ?? 'User'}</p>
            <p className="text-xs text-slate-400 truncate leading-tight">{roleLabel}</p>
          </div>
          <button
            onClick={logout}
            title={t('nav.signOut')}
            className="text-slate-500 hover:text-red-400 transition-colors shrink-0 opacity-0 group-hover:opacity-100"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
