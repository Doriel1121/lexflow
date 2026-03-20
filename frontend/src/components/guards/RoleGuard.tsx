/**
 * components/guards/RoleGuard.tsx
 * =================================
 * Route-level access control component.
 *
 * Usage in App.tsx:
 *
 *   <Route path="/cases" element={
 *     <RoleGuard allowed={['org_admin','lawyer','assistant','viewer']} fallback="/admin">
 *       <CasesPage />
 *     </RoleGuard>
 *   } />
 *
 * How it works:
 *  1. Gets current user from AuthContext
 *  2. Normalizes their role via the central RBAC lib
 *  3. Checks if the role is in `allowed`
 *  4. Redirects to `fallback` (default: '/') if not
 *
 * This component is the ONLY place where route-level access decisions
 * are made. Never replicate this logic in individual page components.
 */

import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { normalizeRole, AppRole } from '../../lib/rbac';

interface RoleGuardProps {
  /** Roles that may access this route. */
  allowed: AppRole[];
  /** Where to send unauthorized users. Defaults to '/'. */
  fallback?: string;
  children: React.ReactNode;
}

export function RoleGuard({ allowed, fallback = '/', children }: RoleGuardProps) {
  const { user, isLoading } = useAuth();

  // While auth state is resolving, render nothing (parent handles loading UI)
  if (isLoading) return null;

  const role = normalizeRole(user?.role);
  if (!allowed.includes(role)) {
    return <Navigate to={fallback} replace />;
  }

  return <>{children}</>;
}

/**
 * Convenience guard: blocks System Admin from accessing tenant pages.
 * Redirects admin → /admin.
 */
export function TenantOnlyGuard({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard
      allowed={['org_admin', 'lawyer', 'assistant', 'viewer']}
      fallback="/admin"
    >
      {children}
    </RoleGuard>
  );
}

/**
 * Convenience guard: blocks tenant users from admin pages.
 * Redirects non-admin → /.
 */
export function AdminOnlyGuard({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard allowed={['admin']} fallback="/">
      {children}
    </RoleGuard>
  );
}
