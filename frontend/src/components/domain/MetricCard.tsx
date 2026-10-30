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
  const accentBorder = {
    primary: 'border-l-brand-primary',
    green: 'border-l-emerald-500',
    amber: 'border-l-amber-500',
    red: 'border-l-red-500',
    purple: 'border-l-purple-500',
  };

  return (
    <div
      className={`bg-bg-surface border border-border-light rounded-xl p-5 shadow-card border-l-4 transition-all duration-150 hover:-translate-y-0.5 flex flex-col justify-between ${accentBorder[accent]} ${className}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          {label}
        </span>
        {icon && <div className="text-text-muted">{icon}</div>}
      </div>

      <div>
        <div className="text-2xl font-bold tracking-tight text-text-primary">
          {value}
        </div>
        {subtext && (
          <p className="text-xs text-text-muted mt-1 leading-snug">
            {subtext}
          </p>
        )}
      </div>
    </div>
  );
};
