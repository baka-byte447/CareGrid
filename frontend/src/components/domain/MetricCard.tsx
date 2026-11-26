import React from 'react';

export interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  subtext?: string;
  icon?: React.ReactNode;
  accent?: 'primary' | 'green' | 'amber' | 'red' | 'purple';
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  icon,
  accent = 'primary',
  className = '',
}) => {
  const iconTone = {
    primary: 'text-brand-primary bg-brand-primary/10',
    purple: 'text-indigo-500 dark:text-indigo-400 bg-indigo-500/10',
    green: 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10',
    amber: 'text-amber-600 dark:text-amber-400 bg-amber-500/10',
    red: 'text-rose-600 dark:text-rose-400 bg-rose-500/10',
  };

  return (
    <div
      className={`glass-panel border border-border-light rounded-2xl p-5 card-interactive flex flex-col justify-between min-h-[118px] ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-text-muted">
          {label}
        </span>
        {icon && (
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${iconTone[accent]}`}>
            {icon}
          </div>
        )}
      </div>

      <div className="mt-3">
        <div className="text-2xl font-bold font-mono tracking-tight text-text-primary">
          {value}
        </div>
        {subtext && (
          <p className="text-[11px] text-text-muted mt-1 leading-snug">
            {subtext}
          </p>
        )}
      </div>
    </div>
  );
};
