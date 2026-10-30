import React from 'react';

export interface StatusDotProps {
  status: 'AVAILABLE' | 'OCCUPIED' | 'MAINTENANCE' | 'IN_USE' | 'WAITING' | 'ADMITTED' | string;
  className?: string;
  pulse?: boolean;
}

export const StatusDot: React.FC<StatusDotProps> = ({ status, className = '', pulse = false }) => {
  const colors: Record<string, string> = {
    AVAILABLE: 'bg-emerald-500',
    OCCUPIED: 'bg-red-500',
    MAINTENANCE: 'bg-amber-500',
    IN_USE: 'bg-blue-500',
    WAITING: 'bg-purple-500',
    ADMITTED: 'bg-emerald-500',
  };

  const color = colors[status] || 'bg-slate-400';

  return (
    <span className={`relative inline-flex items-center justify-center w-2.5 h-2.5 ${className}`}>
      {pulse && (
        <span className={`absolute inline-flex w-full h-full rounded-full opacity-75 animate-ping ${color}`} />
      )}
      <span className={`relative inline-flex rounded-full w-2 h-2 ${color}`} />
    </span>
  );
};
