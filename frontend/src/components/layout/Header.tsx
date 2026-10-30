import React, { useEffect, useState } from 'react';
import { Moon, Sun, RefreshCw, Database } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import { useQueryClient } from '@tanstack/react-query';

export interface HeaderProps {
  hospitalName?: string;
}

export const Header: React.FC<HeaderProps> = ({
  hospitalName = 'St. Jude Central Hospital — Metropolitan Campus',
}) => {
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
        <h2 className="text-sm font-semibold text-text-primary tracking-tight">
          {hospitalName}
        </h2>

        {/* Permanent Synthetic Data Badge (Strict Rule) */}
        <Tooltip content="All patient records, bed occupancy, and telemetry are synthetically simulated for training and testing.">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-800 dark:text-amber-300 border border-amber-500/30 tracking-wide">
            <Database className="w-3 h-3 text-amber-600 dark:text-amber-400" />
            <span>Synthetic Data</span>
          </span>
        </Tooltip>
      </div>

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
