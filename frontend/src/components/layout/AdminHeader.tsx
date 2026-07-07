/**
 * components/layout/AdminHeader.tsx
 * ====================================
 * Slim top-bar for the admin layout.
 * Mirrors the look of the tenant Header but scoped to the admin context:
 *   - Language switcher (LanguageSwitcher component, same as tenant)
 *   - Admin user identity (name + role badge)
 *   - Logout button
 *
 * No search, no "New Case" button — those are tenant-only actions.
 */

import { useRef, useState, useEffect } from 'react';
import { LogOut, ChevronDown, Settings } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { LanguageSwitcher } from '../LanguageSwitcher';

export function AdminHeader() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const getInitials = (name: string) =>
    name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <header className="h-14 bg-white border-b border-slate-100 sticky top-0 z-30 flex items-center justify-between px-6 shadow-sm">
      {/* Left — admin context label */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-primary-700 uppercase tracking-widest select-none">
          {t('adminHeader.systemAdmin', { defaultValue: 'System Admin Console' })}
        </span>
      </div>

      {/* Right — language switcher + user menu */}
      <div className="flex items-center gap-2">
        <LanguageSwitcher />

        <div className="w-px h-5 bg-slate-200 mx-1" />

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 hover:bg-slate-50 px-2 py-1.5 rounded-lg transition-colors"
          >
            {/* Avatar */}
            <div className="h-7 w-7 bg-primary-800 rounded-full flex items-center justify-center text-white font-bold text-xs shrink-0">
              {user ? getInitials(user.name) : 'A'}
            </div>
            {/* Name + role — hidden on small screens */}
            <div className="hidden md:flex flex-col items-start leading-none">
              <span className="text-sm font-semibold text-slate-800">
                {user?.name ?? 'Admin'}
              </span>
              <span className="text-xs font-medium mt-0.5 text-primary-700">
                {t('header.systemAdmin', { defaultValue: 'System Admin' })}
              </span>
            </div>
            <ChevronDown
              className={`h-3.5 w-3.5 text-slate-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`}
            />
          </button>

          {/* Dropdown */}
          {showUserMenu && (
            <div className="absolute end-0 top-full mt-1.5 w-52 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden z-50">
              {/* Identity */}
              <div className="px-4 py-3 border-b border-slate-100">
                <p className="text-sm font-semibold text-slate-800">{user?.name}</p>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{user?.email}</p>
              </div>
              {/* Actions */}
              <div className="py-1">
                <button
                  onClick={() => { navigate('/settings'); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Settings className="h-4 w-4 text-slate-400" />
                  {t('settings.title', { defaultValue: 'Settings' })}
                </button>
              </div>
              <div className="border-t border-slate-100 py-1">
                <button
                  onClick={() => { setShowUserMenu(false); logout(); }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  {t('nav.signOut', { defaultValue: 'Sign out' })}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
