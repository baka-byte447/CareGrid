import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, RefreshCw, LogOut, UserCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/AuthContext';

export const Header: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [isRefreshing, setIsRefreshing] = useState(false);

  const [isDark, setIsDark] = useState(() => {
    return (
      document.documentElement.classList.contains('dark') ||
      window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

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

  return (
    <header className="h-14 bg-bg-surface border-b border-border-light px-6 flex items-center justify-between flex-shrink-0 z-10 transition-colors">

      {/* Left: Refresh and Theme Controls */}
      <div className="flex items-center gap-3">
        <Tooltip content="Refresh all hospital queries from backend">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleManualRefresh}
            isLoading={isRefreshing}
            leftIcon={
              <RefreshCw
                className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`}
              />
            }
            className="text-text-muted hover:text-text-primary"
          >
            Refresh
          </Button>
        </Tooltip>

        <Tooltip content={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
          <button
            onClick={() => setIsDark((prev) => !prev)}
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-surface-hover transition-colors border border-border-light"
            aria-label="Toggle theme"
          >
            {isDark ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-600" />
            )}
          </button>
        </Tooltip>
      </div>

      {/* Right: User Information and Logout */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <UserCircle className="w-5 h-5 text-brand-primary" />

          <div className="flex flex-col">
            <span className="text-xs font-semibold text-text-primary">
              {user?.username ?? 'User'}
            </span>

            <span className="text-[10px] text-text-muted capitalize">
              {user?.role ?? 'Unknown role'}
            </span>
          </div>
        </div>

        <div className="h-7 w-px bg-border-light" />

        <Tooltip content="Sign out of CareGrid">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
            className="text-text-muted hover:text-red-500"
          >
            Logout
          </Button>
        </Tooltip>
      </div>
    </header>
  );
};