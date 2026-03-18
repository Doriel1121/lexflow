import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import './lib/i18n';
import { Layout } from "./components/layout/Layout";
import Dashboard from "./pages/dashboard/Dashboard";
import EmailIntake from "./pages/email/EmailIntake";
import Documents from "./pages/documents/Documents";
import Cases from "./pages/cases/Cases";
import CaseDetailPage from "./pages/CaseDetailPage";
import { DocumentViewer } from "./components/documents/DocumentViewer";
import Settings from "./pages/settings/Settings";
import OrgAuditLogs from "./pages/settings/OrgAuditLogs";
import TeamSettings from "./pages/settings/TeamSettings";
import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import OAuthCallback from "./pages/auth/OAuthCallback";
import AcceptInvite from "./pages/auth/AcceptInvite";
import SearchPage from "./pages/SearchPage";
import { CollectionsList } from "./pages/collections/CollectionsList";
import { CollectionView } from "./pages/collections/CollectionView";
import { ClientsPage } from "./pages/clients/ClientsPage";
import { CreateClientPage } from "./pages/clients/CreateClientPage";
import CreateCasePage from "./pages/CreateCasePage";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import { SnackbarProvider } from "./context/SnackbarContext";
import { AdminLayout } from "./components/layout/AdminLayout";
import AdminDashboard from "./pages/admin/dashboard/AdminDashboard";
import AdminOrganizations from "./pages/admin/organizations/AdminOrganizations";
import AdminUsers from "./pages/admin/users/AdminUsers";
import AdminAuditLogs from "./pages/admin/audit/AdminAuditLogs";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin" />
          <p className="text-slate-500 text-sm font-medium">Loading LegalOS...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <SnackbarProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/auth/callback" element={<OAuthCallback />} />
          <Route path="/auth/accept-invite" element={<AcceptInvite />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="cases" element={<Cases />} />
            <Route path="cases/new" element={<CreateCasePage />} />
            <Route path="cases/:id" element={<CaseDetailPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="clients/new" element={<CreateClientPage />} />
            <Route path="email" element={<EmailIntake />} />
            <Route path="documents" element={<Documents />} />
            <Route path="documents/:id" element={<DocumentViewer />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="collections" element={<CollectionsList />} />
            <Route path="collections/:id" element={<CollectionView />} />
            <Route path="settings" element={<Settings />} />
            <Route path="settings/audit-logs" element={<OrgAuditLogs />} />
            <Route path="team" element={<TeamSettings />} />
          </Route>

          {/* Admin Routes */}
          <Route
            path="/admin"
            element={
              <AdminLayout />
            }
          >
            <Route index element={<AdminDashboard />} />
            <Route path="organizations" element={<AdminOrganizations />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="audit-logs" element={<AdminAuditLogs />} />
          </Route>

          {/* Catch-all: redirect unknown routes to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
        </SnackbarProvider>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default App;
