import React, { useEffect, useState } from 'react';
import { Moon, Sun, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import { useQueryClient } from '@tanstack/react-query';

export const Header: React.FC = () => {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDark, setIsDark] = useState(() => {
    return document.documentElement.classList.contains('dark') ||
      window.matchMedia('(prefers-color-scheme: dark)').matches;
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

  return (
    <header className="h-14 bg-bg-surface border-b border-border-light px-6 flex items-center justify-between flex-shrink-0 z-10 transition-colors">
      <div className="flex items-center gap-3">
        {/* Manual Data Refresh Button */}
        <Tooltip content="Refresh all hospital queries from backend">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleManualRefresh}
            isLoading={isRefreshing}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />}
            className="text-text-muted hover:text-text-primary"
          >
            Refresh
          </Button>
        </Tooltip>

        {/* Dark/Light Theme Toggle */}
        <Tooltip content={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
          <button
            onClick={() => setIsDark((prev) => !prev)}
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-surface-hover transition-colors border border-border-light"
            aria-label="Toggle theme"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-600" />}
          </button>
        </Tooltip>
      </div>
    </header>
  );
};
