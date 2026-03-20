/**
 * components/layout/AdminLayout.tsx  —  REDESIGNED (v2)
 * =======================================================
 * Shell for all /admin/* pages.
 *
 * Auth + role enforcement is handled UPSTREAM by AdminOnlyGuard in App.tsx.
 * This component only handles layout — it trusts that the guard has already
 * verified the user is a system admin before mounting this shell.
 *
 * Uses the shared Sidebar, which is role-aware and will automatically
 * show only the admin nav group for admin users.
 */

import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useTranslation } from 'react-i18next';

export function AdminLayout() {
  const { i18n } = useTranslation();
  const isRTL = i18n.language === 'he';

  return (
    <div className="flex min-h-screen bg-slate-50" dir={isRTL ? 'rtl' : 'ltr'}>
      <Sidebar />
      <main className="flex-1 ps-60 overflow-y-auto">
        {/* Purple top bar to visually distinguish the admin context */}
        <div className="h-1 w-full bg-gradient-to-r from-purple-600 via-violet-500 to-indigo-600" />
        <div className="p-8">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
