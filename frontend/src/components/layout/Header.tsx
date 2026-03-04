import React, { useState, useRef, useEffect } from 'react';
import { Search, Plus, LogOut, User, Settings, ChevronDown, Shield } from 'lucide-react';
import { NotificationDropdown } from '../Notifications/NotificationDropdown';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const roleLabel = user?.role
    ? (user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase())
    : 'User';

  const roleColor: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-700',
    ADMIN: 'bg-purple-100 text-purple-700',
    lawyer: 'bg-blue-100 text-blue-700',
    LAWYER: 'bg-blue-100 text-blue-700',
    assistant: 'bg-green-100 text-green-700',
    ASSISTANT: 'bg-green-100 text-green-700',
    viewer: 'bg-slate-100 text-slate-600',
    VIEWER: 'bg-slate-100 text-slate-600',
  };

  return (
    <header className="h-16 bg-background border-b border-border sticky top-0 z-10 flex items-center justify-between px-6">
      {/* Search */}
      <div className="flex items-center w-96">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search cases, documents, clients..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearch}
            className="w-full pl-10 pr-4 py-2 bg-muted/50 border border-transparent focus:bg-background focus:border-primary rounded-full text-sm outline-none transition-all duration-200"
          />
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center space-x-3">
        <button
          onClick={() => navigate('/cases')}
          className="flex items-center space-x-2 bg-primary text-primary-foreground px-4 py-2 rounded-full text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm"
        >
          <Plus className="h-4 w-4" />
          <span>New Case</span>
        </button>

        <NotificationDropdown />

        <div className="h-8 w-[1px] bg-border mx-1" />

        {/* User Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center space-x-2 hover:bg-muted px-2 py-1.5 rounded-xl transition-colors"
            title={user?.email}
          >
            <div className="h-8 w-8 bg-primary/10 rounded-full flex items-center justify-center text-primary font-bold text-sm border border-primary/20">
              {user ? getInitials(user.name) : 'U'}
            </div>
            <div className="hidden md:flex flex-col items-start">
              <span className="text-sm font-medium text-slate-800 leading-none">{user?.name ?? 'User'}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded mt-0.5 font-medium leading-none ${roleColor[user?.role ?? 'viewer'] ?? 'bg-slate-100 text-slate-600'}`}>
                {roleLabel}
              </span>
            </div>
            <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
          </button>

          {showUserMenu && (
            <div className="absolute right-0 top-full mt-2 w-64 bg-white border border-border rounded-xl shadow-lg overflow-hidden z-50">
              {/* User info header */}
              <div className="px-4 py-3 bg-slate-50 border-b border-border">
                <p className="text-sm font-semibold text-slate-800">{user?.name}</p>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{user?.email}</p>
                <span className={`inline-block mt-1.5 text-xs px-2 py-0.5 rounded-full font-medium ${roleColor[user?.role ?? 'viewer'] ?? 'bg-slate-100 text-slate-600'}`}>
                  <Shield className="inline h-3 w-3 mr-1" />{roleLabel}
                </span>
              </div>

              {/* Menu items */}
              <div className="py-1">
                <button
                  onClick={() => { navigate('/settings'); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <User className="h-4 w-4 text-slate-400" />
                  Profile & Settings
                </button>
                <button
                  onClick={() => { navigate('/settings'); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Settings className="h-4 w-4 text-slate-400" />
                  Preferences
                </button>
              </div>

              <div className="border-t border-border py-1">
                <button
                  onClick={() => { setShowUserMenu(false); logout(); }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-destructive hover:bg-destructive/5 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
