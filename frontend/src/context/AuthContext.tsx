import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../services/api';
import api from '../services/api';

export interface User {
  id: number;
  name: string;
  email: string;
  role: 'admin' | 'lawyer' | 'assistant' | 'viewer' | 'ADMIN' | 'LAWYER' | 'ASSISTANT' | 'VIEWER';
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
      setUser({
        id: userData.id,
        name: userData.full_name || userData.email,
        email: userData.email,
        role: userData.role || 'lawyer',
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
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, refreshUser, isLoading }}>
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
