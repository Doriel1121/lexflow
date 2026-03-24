import React from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

import LoginPage from "../pages/LoginPage";
import AuthCallback from "../pages/AuthCallback";
import DashboardPage from "../pages/DashboardPage";
import CreateCasePage from "../pages/CreateCasePage";
import CaseDetailPage from "../pages/CaseDetailPage";
import DocumentsPage from "../pages/DocumentsPage";
import SearchPage from "../pages/SearchPage";
import Settings from "../pages/settings/Settings";
import EmailIntake from "../pages/email/EmailIntake";
import { ClientsPage } from "../pages/clients/ClientsPage";
import { CreateClientPage } from "../pages/clients/CreateClientPage";
import NotFoundPage from "../pages/NotFoundPage"; // To be created
import Cases from "@/pages/cases/Cases";

interface ProtectedRouteProps {
  children?: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />; // Render child routes if authenticated
};

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Protected Routes */}
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/cases/new" element={<CreateCasePage />} />
        <Route path="/cases/:id" element={<CaseDetailPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/clients/new" element={<CreateClientPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/email" element={<EmailIntake />} />
        {/* Add more protected routes here */}
      </Route>

      {/* Catch-all for 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};

export default AppRoutes;
