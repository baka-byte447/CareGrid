import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  error?: Error | null;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load hospital data',
  message,
  error,
  onRetry,
  className = '',
}) => {
  const displayMessage = message || error?.message || 'A network error occurred or the backend service is currently unreachable.';

  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center p-8 text-center bg-red-500/5 border border-red-500/20 rounded-xl my-4 ${className}`}
    >
      <div className="p-3 mb-3 text-red-600 dark:text-red-400 bg-red-500/10 rounded-full">
        <AlertTriangle className="w-8 h-8" />
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-xs text-text-secondary max-w-md mb-4 leading-relaxed font-mono bg-bg-surface px-3 py-2 rounded border border-border-light">
        {displayMessage}
      </p>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Retry Connection
        </Button>
      )}
    </div>
  );
};
