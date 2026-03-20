/**
 * context/AuthContext.tsx  —  REDESIGNED (v2)
 * =============================================
 * Changes from v1:
 *   - `user.role` is now always a canonical lowercase AppRole.
 *     normalizeRole() is applied at the API boundary so no component
 *     ever needs to handle 'ADMIN', 'ORG_ADMIN', etc.
 *   - `isSystemAdmin` helper added to context for quick checks.
 *   - `isTenantUser` helper added.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../services/api';
import api from '../services/api';
import { normalizeRole, AppRole, isSystemAdmin, isTenantUser } from '../lib/rbac';

export interface User {
  id: number;
  name: string;
  email: string;
  /** Always a canonical lowercase role — never 'ADMIN', 'ORG_ADMIN', etc. */
  role: AppRole;
  is_superuser?: boolean;
  organization?: {
    id: number;
    name: string;
    slug: string;
  };
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  /** True only for role === 'admin' (system-level administrator). */
  isSystemAdmin: boolean;
  /** True for org_admin, lawyer, assistant, viewer — any tenant user. */
  isTenantUser: boolean;
  login: (provider: string) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUserInfo = useCallback(async () => {
    try {
      const response = await api.get('/v1/users/me');
      const userData = response.data;

      // ── Normalize role at the API boundary ──────────────────────────
      // From this point on, user.role is always a canonical AppRole.
      const canonicalRole = normalizeRole(userData.role);

      setUser({
        id: userData.id,
        name: userData.full_name || userData.email,
        email: userData.email,
        role: canonicalRole,
        is_superuser: userData.is_superuser || false,
        organization: userData.organization || undefined,
      });
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Failed to fetch user info:', error);
      localStorage.removeItem('access_token');
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      fetchUserInfo();
    } else {
      setIsLoading(false);
    }
  }, [fetchUserInfo]);

  const refreshUser = useCallback(async () => {
    await fetchUserInfo();
  }, [fetchUserInfo]);

  const login = (provider: string) => {
    window.location.href = `${API_BASE_URL}/v1/auth/login/${provider}`;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
    setIsAuthenticated(false);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{
      isAuthenticated,
      user,
      isSystemAdmin: isSystemAdmin(user?.role),
      isTenantUser: isTenantUser(user?.role),
      login,
      logout,
      refreshUser,
      isLoading,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
