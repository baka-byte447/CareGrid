import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export interface StaleBannerProps {
  isStale: boolean;
  isError?: boolean;
  lastUpdated?: number | null;
  onRefresh?: () => void;
}

export const StaleBanner: React.FC<StaleBannerProps> = ({
  isStale,
  isError = false,
  lastUpdated,
  onRefresh,
}) => {
  if (!isStale && !isError) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="bg-amber-500/15 border-b border-amber-500/30 text-amber-900 dark:text-amber-200 px-4 py-2.5 flex items-center justify-between text-xs transition-all duration-200"
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 animate-pulse" />
        <span>
          {isError ? (
            <strong>Network warning: Backend is currently unreachable. Displaying cached hospital state.</strong>
          ) : (
            <strong>Hospital data may be stale: Last synchronization was over 2 minutes ago.</strong>
          )}
          {lastUpdated && (
            <span className="ml-1 opacity-80">
              (Cached at {new Date(lastUpdated).toLocaleTimeString()})
            </span>
          )}
        </span>
      </div>
      {onRefresh && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          className="border-amber-500/40 hover:bg-amber-500/20 text-amber-900 dark:text-amber-200 h-7 text-[11px]"
          leftIcon={<RefreshCw className="w-3 h-3" />}
        >
          Refresh Now
        </Button>
      )}
    </div>
  );
};
