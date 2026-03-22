/**
 * App.tsx  —  REDESIGNED (v2)
 * ============================
 * Route configuration with full RBAC enforcement.
 *
 * Guard hierarchy:
 *
 *   /login, /register       → public (no auth required)
 *   /*                      → ProtectedRoute (must be authenticated)
 *     /admin/*              → AdminOnlyGuard (role === 'admin' only)
 *       AdminLayout         → wraps all /admin pages
 *     /*                    → Layout (tenant shell)
 *       /clients            → TenantOnlyGuard (admin is BLOCKED)
 *       /cases              → TenantOnlyGuard
 *       /documents          → TenantOnlyGuard
 *       /email              → TenantOnlyGuard
 *       /collections        → TenantOnlyGuard
 *       /team               → RoleGuard(['org_admin'])
 *       /settings/audit-logs → RoleGuard(['org_admin'])
 *       /search, /settings, / → all authenticated users
 *
 * When System Admin logs in:
 *   - They land on /admin (their home)
 *   - Any attempt to visit /clients, /cases, /documents → redirected to /admin
 *   - The sidebar only shows admin nav items (enforced in Sidebar.tsx)
 *   - The tenant Layout is never rendered for them
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './lib/i18n';

// ── Layout shells ────────────────────────────────────────────────────────
import { Layout } from './components/layout/Layout';
import { AdminLayout } from './components/layout/AdminLayout';

// ── Guards ───────────────────────────────────────────────────────────────
import { RoleGuard, TenantOnlyGuard, AdminOnlyGuard } from './components/guards/RoleGuard';

// ── Auth pages ───────────────────────────────────────────────────────────
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import OAuthCallback from './pages/auth/OAuthCallback';
import AcceptInvite from './pages/auth/AcceptInvite';

// ── Tenant pages ─────────────────────────────────────────────────────────
import Dashboard from './pages/dashboard/Dashboard';
import EmailIntake from './pages/email/EmailIntake';
import Documents from './pages/documents/Documents';
import Cases from './pages/cases/Cases';
import CaseDetailPage from './pages/CaseDetailPage';
import { DocumentViewer } from './components/documents/DocumentViewer';
import Settings from './pages/settings/Settings';
import OrgAuditLogs from './pages/settings/OrgAuditLogs';
import TeamSettings from './pages/settings/TeamSettings';
import SearchPage from './pages/SearchPage';
import { CollectionsList } from './pages/collections/CollectionsList';
import { CollectionView } from './pages/collections/CollectionView';
import { ClientsPage } from './pages/clients/ClientsPage';
import { CreateClientPage } from './pages/clients/CreateClientPage';
import CreateCasePage from './pages/CreateCasePage';

// ── Admin pages ───────────────────────────────────────────────────────────
import AdminDashboard from './pages/admin/dashboard/AdminDashboard';
import AdminOrganizations from './pages/admin/organizations/AdminOrganizations';
import AdminUsers from './pages/admin/users/AdminUsers';
import AdminAuditLogs from './pages/admin/audit/AdminAuditLogs';

// ── Providers ────────────────────────────────────────────────────────────
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import { SnackbarProvider } from './context/SnackbarContext';

import { normalizeRole } from './lib/rbac';
import CasesPage from './pages/CasesPage';

// ─── Loading screen ───────────────────────────────────────────────────────

function LoadingScreen() {
  return (
    <div className="h-screen flex items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin" />
        <p className="text-slate-500 text-sm font-medium">Loading LegalOS…</p>
      </div>
    </div>
  );
}

// ─── Auth gate ────────────────────────────────────────────────────────────

/**
 * Ensures the user is authenticated.
 * If not authenticated → /login.
 * Once authenticated, routes System Admin directly to /admin
 * so they never land on the tenant shell by mistake.
 */
function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) return <LoadingScreen />;

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  // System Admin trying to access the root → send to /admin
  if (normalizeRole(user?.role) === 'admin') {
    // Only redirect if not already on an /admin path
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/admin')) {
      return <Navigate to="/admin" replace />;
    }
  }

  return <>{children}</>;
}

// ─── Route tree ───────────────────────────────────────────────────────────

function AppRoutes() {
  return (
    <Routes>
      {/* ── Public routes ─────────────────────────────────────────────── */}
      <Route path="/login"              element={<Login />} />
      <Route path="/register"           element={<Register />} />
      <Route path="/auth/callback"      element={<OAuthCallback />} />
      <Route path="/auth/accept-invite" element={<AcceptInvite />} />

      {/* ── System Admin routes ───────────────────────────────────────── */}
      {/*
       * AdminOnlyGuard: if a tenant user somehow navigates here,
       * they are redirected to / (their home).
       *
       * The AdminLayout renders its own sidebar with only admin nav items.
       * The tenant Layout is never mounted for admin users.
       */}
      <Route
        path="/admin"
        element={
          <AuthGate>
            <AdminOnlyGuard>
              <AdminLayout />
            </AdminOnlyGuard>
          </AuthGate>
        }
      >
        <Route index            element={<AdminDashboard />} />
        <Route path="organizations" element={<AdminOrganizations />} />
        <Route path="users"         element={<AdminUsers />} />
        <Route path="audit-logs"    element={<AdminAuditLogs />} />
      </Route>

      {/* ── Tenant routes ─────────────────────────────────────────────── */}
      {/*
       * All wrapped in AuthGate (must be authenticated).
       * Specific pages wrapped in TenantOnlyGuard or RoleGuard
       * where additional role checks are needed.
       *
       * System Admin attempting to visit any of these routes
       * will be redirected to /admin by TenantOnlyGuard.
       */}
      <Route
        path="/"
        element={
          <AuthGate>
            {/* TenantOnlyGuard on the Layout level means admin
                NEVER gets the tenant shell, even for allowed paths */}
            <TenantOnlyGuard>
              <Layout />
            </TenantOnlyGuard>
          </AuthGate>
        }
      >
        {/* ── Open to all tenant users ────────────────────────────────── */}
        <Route index element={<Dashboard />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="settings" element={<Settings />} />

        {/* ── Tenant-only pages (admin blocked, redirected to /admin) ─── */}
        <Route path="cases"     element={<TenantOnlyGuard><Cases /></TenantOnlyGuard>} />
        <Route path="cases/new" element={<TenantOnlyGuard><CreateCasePage /></TenantOnlyGuard>} />
        <Route path="cases/:id" element={<TenantOnlyGuard><CaseDetailPage /></TenantOnlyGuard>} />

        <Route path="clients"   element={<TenantOnlyGuard><ClientsPage /></TenantOnlyGuard>} />
        <Route path="clients/new" element={<TenantOnlyGuard><CreateClientPage /></TenantOnlyGuard>} />

        <Route path="documents"    element={<TenantOnlyGuard><Documents /></TenantOnlyGuard>} />
        <Route path="documents/:id" element={<TenantOnlyGuard><DocumentViewer /></TenantOnlyGuard>} />

        <Route path="email"       element={<TenantOnlyGuard><EmailIntake /></TenantOnlyGuard>} />
        <Route path="collections" element={<TenantOnlyGuard><CollectionsList /></TenantOnlyGuard>} />
        <Route path="collections/:id" element={<TenantOnlyGuard><CollectionView /></TenantOnlyGuard>} />

        {/* ── Org Admin only ──────────────────────────────────────────── */}
        <Route
          path="team"
          element={
            <RoleGuard allowed={['org_admin']} fallback="/">
              <TeamSettings />
            </RoleGuard>
          }
        />
        <Route
          path="settings/audit-logs"
          element={
            <RoleGuard allowed={['org_admin']} fallback="/settings">
              <OrgAuditLogs />
            </RoleGuard>
          }
        />
      </Route>

      {/* ── Catch-all ─────────────────────────────────────────────────── */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <SnackbarProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </SnackbarProvider>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default App;
