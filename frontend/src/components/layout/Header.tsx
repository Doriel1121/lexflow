import React, { useState, useRef, useEffect } from 'react';
import { Search, Plus, LogOut, Settings, ChevronDown } from 'lucide-react';
import { NotificationDropdown } from '../Notifications/NotificationDropdown';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '../LanguageSwitcher';

export function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name: string) =>
    name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const roleLabel = user?.role
    ? ((user.role as string) === 'ORG_ADMIN' ? 'Org Admin' : user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase())
    : 'User';

  const roleColor: Record<string, string> = {
    admin: 'text-purple-600', ADMIN: 'text-purple-600',
    org_admin: 'text-indigo-600', ORG_ADMIN: 'text-indigo-600',
    lawyer: 'text-blue-600', LAWYER: 'text-blue-600',
    assistant: 'text-green-600', ASSISTANT: 'text-green-600',
  };

  return (
    <header className="h-14 bg-white border-b border-slate-100 sticky top-0 z-30 flex items-center justify-between px-6 shadow-sm">
      {/* Search */}
      <div className="flex items-center w-80">
        <div className="relative w-full">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder={t('header.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearch}
            className="w-full ps-9 pe-4 py-1.5 bg-slate-50 border border-slate-200 focus:bg-white focus:border-slate-300 rounded-lg text-sm outline-none transition-all duration-200 placeholder:text-slate-400"
          />
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => navigate('/cases/new')}
          className="flex items-center gap-1.5 bg-slate-900 text-white px-3.5 py-1.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          {t('header.newCase')}
        </button>

        <NotificationDropdown />
        <LanguageSwitcher />

        <div className="w-px h-5 bg-slate-200 mx-1" />

        {/* User Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 hover:bg-slate-50 px-2 py-1.5 rounded-lg transition-colors"
          >
            <div className="h-7 w-7 bg-slate-800 rounded-full flex items-center justify-center text-white font-bold text-xs">
              {user ? getInitials(user.name) : 'U'}
            </div>
            <div className="hidden md:flex flex-col items-start leading-none">
              <span className="text-sm font-semibold text-slate-800">{user?.name ?? 'User'}</span>
              <span className={`text-xs font-medium mt-0.5 ${roleColor[user?.role ?? ''] ?? 'text-slate-500'}`}>
                {roleLabel}
              </span>
            </div>
            <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
          </button>

          {showUserMenu && (
            <div className="absolute end-0 top-full mt-1.5 w-56 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-slate-100">
                <p className="text-sm font-semibold text-slate-800">{user?.name}</p>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                <button
                  onClick={() => { navigate('/settings'); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Settings className="h-4 w-4 text-slate-400" />
                  {t('settings.title')}
                </button>
              </div>
              <div className="border-t border-slate-100 py-1">
                <button
                  onClick={() => { setShowUserMenu(false); logout(); }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  {t('nav.signOut')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
