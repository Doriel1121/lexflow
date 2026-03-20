/**
 * components/layout/Sidebar.tsx  —  REDESIGNED (v2)
 * ====================================================
 * Role-aware sidebar that derives its navigation purely from
 * the RBAC permission table in lib/rbac.ts.
 *
 * Rules:
 *   - System Admin (role === 'admin') ONLY sees admin nav items.
 *   - Tenant users NEVER see admin nav items.
 *   - Each group/item is filtered by `getNavForRole()` from lib/rbac.ts.
 *   - No nav items are hardcoded per role in this file.
 *
 * Adding or removing nav items for a role → edit lib/rbac.ts only.
 */

import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Inbox, Files, Settings, Scale, Briefcase, LogOut,
  Search, Building2, Users, ClipboardList, FolderGit2,
  ShieldCheck, ChevronDown, ChevronRight, Activity,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { normalizeRole, getNavForRole, NavGroupDef } from '../../lib/rbac';

// ─── Icon registry ─────────────────────────────────────────────────────────
// Maps the string icon names in rbac.ts to actual Lucide components.
// Add here whenever a new icon is added to NAV_GROUPS.

const ICON_MAP: Record<string, React.ElementType> = {
  LayoutDashboard,
  Inbox,
  Files,
  Settings,
  Scale,
  Briefcase,
  LogOut,
  Search,
  Building2,
  Users,
  ClipboardList,
  FolderGit2,
  ShieldCheck,
  Activity,
};

const roleColors: Record<string, string> = {
  admin:     'bg-purple-500',
  org_admin: 'bg-indigo-500',
  lawyer:    'bg-blue-500',
  assistant: 'bg-green-500',
  viewer:    'bg-slate-500',
};

// ─── Nav group section ──────────────────────────────────────────────────────

function NavGroupSection({ group, isAdmin }: { group: NavGroupDef; isAdmin: boolean }) {
  const [open, setOpen] = useState(group.defaultOpen ?? true);
  const { t } = useTranslation();

  if (group.items.length === 0) return null;

  const activeClass = isAdmin
    ? 'bg-purple-600/30 text-purple-200'
    : 'bg-white/10 text-white';

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
          {group.items.map((item) => {
            const Icon = ICON_MAP[item.icon] ?? LayoutDashboard;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-sm font-medium',
                    isActive
                      ? activeClass
                      : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{t(item.labelKey)}</span>
              </NavLink>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Sidebar ────────────────────────────────────────────────────────────────

export function Sidebar() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();

  const role = normalizeRole(user?.role);
  const isAdmin = role === 'admin';

  // Get only the nav groups this role is allowed to see.
  // getNavForRole() reads from lib/rbac.ts — no logic duplicated here.
  const navGroups = getNavForRole(role);

  const getInitials = (name: string) =>
    name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  const roleLabel =
    role === 'org_admin' ? t('header.orgAdmin') :
    role === 'admin'     ? t('header.systemAdmin', { defaultValue: 'System Admin' }) :
    (user?.role ?? 'User');

  return (
    <aside className="h-screen w-60 bg-slate-900 text-white flex flex-col fixed start-0 top-0">

      {/* Logo + role indicator */}
      <div className="px-4 py-5 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="bg-primary p-1.5 rounded-lg shrink-0">
            <Scale className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-serif text-lg font-bold tracking-tight">LegalOS</span>
        </div>
        {/* Role mode badge */}
        {isAdmin && (
          <div className="mt-3 px-2 py-1 rounded-md bg-purple-500/20 border border-purple-500/30">
            <p className="text-xs text-purple-300 font-semibold text-center tracking-wide">
              ⚙ System Admin Mode
            </p>
          </div>
        )}
      </div>

      {/* Navigation — purely role-driven */}
      <nav className="flex-1 p-3 overflow-y-auto space-y-3">
        {navGroups.map(group => (
          <NavGroupSection
            key={group.labelKey}
            group={group}
            isAdmin={isAdmin}
          />
        ))}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-white/5 shrink-0">
        {/* Show org name only for tenant users — admin has no org context */}
        {!isAdmin && user?.organization && (
          <div className="mb-2 px-2 py-1.5 rounded-lg bg-indigo-500/10">
            <p className="text-xs text-indigo-400 truncate font-medium">
              {user.organization.name}
            </p>
          </div>
        )}

        <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-white/5 transition-colors group">
          <div className={cn(
            'h-8 w-8 rounded-full flex items-center justify-center text-white font-bold text-xs shrink-0',
            roleColors[role] ?? 'bg-slate-500',
          )}>
            {user ? getInitials(user.name) : 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate leading-tight">
              {user?.name ?? 'User'}
            </p>
            <p className="text-xs text-slate-400 truncate leading-tight capitalize">
              {roleLabel}
            </p>
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
