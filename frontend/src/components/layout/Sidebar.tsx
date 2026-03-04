
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Inbox, Files, Settings, Scale, Briefcase, LogOut, Search, Activity, Building2, Users, ClipboardList, FolderGit2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAuth } from '../../context/AuthContext';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Building2, label: 'Clients', path: '/clients' },
  { icon: Briefcase, label: 'Cases', path: '/cases' },
  { icon: Inbox, label: 'Email Intake', path: '/email' },
  { icon: Files, label: 'Documents', path: '/documents' },
  { icon: FolderGit2, label: 'Collections', path: '/collections' },
  { icon: Search, label: 'Search', path: '/search' },
  { icon: Users, label: 'Team', path: '/team', role: ['ORG_ADMIN', 'ADMIN'] },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

const roleColors: Record<string, string> = {
  admin: 'bg-purple-500',
  ADMIN: 'bg-purple-500',
  lawyer: 'bg-blue-500',
  LAWYER: 'bg-blue-500',
  assistant: 'bg-green-500',
  ASSISTANT: 'bg-green-500',
  viewer: 'bg-slate-500',
  VIEWER: 'bg-slate-500',
};

export function Sidebar() {
  const { user, logout } = useAuth();

  const getInitials = (name: string) =>
    name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  const roleLabel = user?.role
    ? user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase()
    : 'User';

  return (
    <aside className="h-screen w-64 bg-slate-900 text-white flex flex-col fixed left-0 top-0 border-r border-slate-800">
      {/* Logo */}
      <div className="p-6 flex items-center space-x-3 border-b border-slate-800 shrink-0">
        <div className="bg-primary p-2 rounded-lg">
          <Scale className="h-6 w-6 text-primary-foreground" />
        </div>
        <span className="font-serif text-xl font-bold tracking-tight">LexFlow</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          if (item.role) {
            const userRoleUppercased = (user?.role || '').toUpperCase();
            const allowedRolesUppercased = item.role.map(r => r.toUpperCase());
            if (!allowedRolesUppercased.includes(userRoleUppercased)) return null;
          }
          
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 group',
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/20'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <item.icon className="h-5 w-5 shrink-0" />
              <span className="font-medium">{item.label}</span>
            </NavLink>
          );
        })}

        {/* Admin Navigation */}
        {(user?.role === 'admin' || user?.role === 'ADMIN' || user?.is_superuser) && (
          <div className="pt-4 mt-4 border-t border-slate-800">
            <p className="px-4 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Backoffice</p>
            
            <NavLink
              to="/admin"
              end
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 group',
                  isActive
                    ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/50'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <Activity className="h-5 w-5 shrink-0" />
              <span className="font-medium">System Overview</span>
            </NavLink>

            <NavLink
              to="/admin/organizations"
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 group mt-1',
                  isActive
                    ? 'bg-purple-600/50 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <Building2 className="h-5 w-5 shrink-0" />
              <span className="font-medium">Organizations</span>
            </NavLink>

            <NavLink
              to="/admin/users"
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 group mt-1',
                  isActive
                    ? 'bg-purple-600/50 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <Users className="h-5 w-5 shrink-0" />
              <span className="font-medium">Users & Roles</span>
            </NavLink>

            <NavLink
              to="/admin/audit-logs"
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 group mt-1',
                  isActive
                    ? 'bg-purple-600/50 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <ClipboardList className="h-5 w-5 shrink-0" />
              <span className="font-medium">Audit Logs</span>
            </NavLink>
          </div>
        )}
      </nav>

      {/* User Profile Footer */}
      <div className="p-4 border-t border-slate-800 shrink-0">
        {user?.organization && (
          <div className="mb-3 px-3 py-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
            <p className="text-xs text-indigo-400 font-medium uppercase tracking-wider mb-0.5">Organization</p>
            <p className="text-sm text-indigo-300 font-semibold truncate">{user.organization.name}</p>
          </div>
        )}
        <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 transition-colors">
          <div className={cn('h-9 w-9 rounded-full flex items-center justify-center text-white font-bold text-sm shrink-0', roleColors[user?.role ?? 'viewer'] ?? 'bg-slate-500')}>
            {user ? getInitials(user.name) : 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate">{user?.name ?? 'User'}</p>
            <p className="text-xs text-slate-400 truncate">{roleLabel}</p>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="text-slate-400 hover:text-red-400 transition-colors shrink-0 p-1"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
