import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Sidebar } from "./Sidebar";
import { useTranslation } from "react-i18next";

export function AdminLayout() {
  const { isAuthenticated, user, isLoading } = useAuth();
  const { i18n } = useTranslation();
  const isRTL = i18n.language === 'he';

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin" />
          <p className="text-slate-500 text-sm font-medium">Loading Admin Panel...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Double check admin role
  if (user?.role !== "admin" && user?.role !== "ADMIN") {
    // Redirect non-admins back to standard dashboard
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex min-h-screen bg-slate-50" dir={isRTL ? 'rtl' : 'ltr'}>
      <Sidebar />
      <main className="flex-1 ps-60 p-8 overflow-y-auto">
        <div className="max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
