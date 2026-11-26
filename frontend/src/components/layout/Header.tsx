import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, RefreshCw, LogOut, Search } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/AuthContext';

export const Header: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [quickSearch, setQuickSearch] = useState('');

  const [isDark, setIsDark] = useState(() => {
    return document.documentElement.classList.contains('dark');
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate('/login', { replace: true });
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickSearch.trim()) return;
    navigate(`/queue?q=${encodeURIComponent(quickSearch.trim())}`);
  };

  const initials = (user?.username ?? 'U').slice(0, 2).toUpperCase();

  return (
    <header className="h-[68px] glass border-b border-border-light px-6 flex items-center justify-between flex-shrink-0 z-10 sticky top-0 transition-colors">

      {/* Left: Cosmic Search Bar with Ctrl + K */}
      <form onSubmit={handleSearchSubmit} className="hidden md:flex items-center w-80 lg:w-96">
        <div className="relative w-full">
          <Search className="w-3.5 h-3.5 text-text-muted absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            ref={searchInputRef}
            type="text"
            value={quickSearch}
            onChange={(e) => setQuickSearch(e.target.value)}
            placeholder="Search patients, beds, or wards..."
            className="w-full h-9 pl-9 pr-16 rounded-xl bg-bg-surface border border-border-light text-xs text-text-primary placeholder:text-text-muted shadow-xs focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/20 transition-all"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-text-muted bg-bg-surface-hover border border-border-light rounded">
            Ctrl+K
          </kbd>
        </div>
      </form>

      {/* Right: Circular Utility Buttons + Profile Pill */}
      <div className="flex items-center gap-2.5 ml-auto">
        <Tooltip content="Refresh all hospital queries from backend">
          <button
            type="button"
            onClick={handleManualRefresh}
            className="w-9 h-9 rounded-full bg-bg-surface border border-border-light flex items-center justify-center text-text-secondary hover:text-brand-primary hover:border-brand-primary/40 shadow-xs transition-all"
            aria-label="Refresh data"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-brand-primary' : ''}`} />
          </button>
        </Tooltip>

        <Tooltip content={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
          <button
            type="button"
            onClick={() => setIsDark((prev) => !prev)}
            className="w-9 h-9 rounded-full bg-bg-surface border border-border-light flex items-center justify-center text-text-secondary hover:text-brand-primary hover:border-brand-primary/40 shadow-xs transition-all"
            aria-label="Toggle theme"
          >
            {isDark ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-violet-600" />
            )}
          </button>
        </Tooltip>

        <div className="h-6 w-px bg-border-light mx-1" />

        <div className="flex items-center gap-2.5 pr-1">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-xs"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {initials}
          </div>

          <div className="hidden sm:flex flex-col">
            <span className="text-xs font-bold text-text-primary leading-tight">
              {user?.username ?? 'User'}
            </span>
            <span className="text-[10px] text-text-muted capitalize">
              {user?.role ?? 'Clinician'}
            </span>
          </div>
        </div>

        <Tooltip content="Sign out of CareGrid">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
            className="text-text-muted hover:text-rose-500 rounded-full"
          >
            Logout
          </Button>
        </Tooltip>
      </div>
    </header>
  );
};