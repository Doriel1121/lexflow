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
import { AdminHeader } from './AdminHeader';
import { useTranslation } from 'react-i18next';

export function AdminLayout() {
  const { i18n } = useTranslation();
  const isRTL = i18n.language === 'he';

  return (
    <div className="flex min-h-screen bg-slate-50" dir={isRTL ? 'rtl' : 'ltr'}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-h-screen ps-60">
        <AdminHeader />
        {/* Brand top bar — navy-to-gold gradient distinguishes admin context */}
        <div className="h-1 w-full bg-gradient-to-r from-primary-900 via-primary-700 to-secondary-500" />
        <main className="flex-1 px-8 py-6 overflow-y-auto">
          <div className="max-w-7xl mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
