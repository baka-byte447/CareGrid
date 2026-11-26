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
  const kpiTheme = {
    primary: 'kpi-cyan',
    purple: 'kpi-purple',
    green: 'kpi-emerald',
    amber: 'kpi-amber',
    red: 'kpi-amber',
  };

  const iconBubble = {
    primary: 'bg-sky-500/20 text-sky-400 border-sky-400/40',
    purple: 'bg-purple-500/20 text-purple-400 border-purple-400/40',
    green: 'bg-emerald-500/20 text-emerald-400 border-emerald-400/40',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-400/40',
    red: 'bg-rose-500/20 text-rose-400 border-rose-400/40',
  };

  const sparkColor = {
    primary: '#38bdf8',
    purple: '#a855f7',
    green: '#34d399',
    amber: '#fbbf24',
    red: '#fb7185',
  };

  return (
    <div
      className={`relative overflow-hidden border rounded-2xl p-4 backdrop-blur-md card-interactive flex flex-col justify-between min-h-[124px] ${kpiTheme[accent]} ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {icon && (
            <div
              className={`w-10 h-10 rounded-full border flex items-center justify-center flex-shrink-0 ${iconBubble[accent]}`}
            >
              {icon}
            </div>
          )}
          <div>
            <span className="text-xs font-medium text-text-secondary block">
              {label}
            </span>
            <div className="text-2xl font-bold font-mono tracking-tight text-text-primary mt-0.5">
              {value}
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-end justify-between gap-2 mt-2">
        {subtext ? (
          <p className="text-[11px] font-medium text-text-muted leading-snug">
            {subtext}
          </p>
        ) : (
          <span />
        )}

        {/* Mini Sparkline Wave (Reference Inspired) */}
        <svg className="w-16 h-7 flex-shrink-0 opacity-85" viewBox="0 0 64 28" fill="none">
          <path
            d="M2 24 C10 24, 14 14, 22 16 C30 18, 34 8, 42 12 C50 16, 54 4, 62 6"
            stroke={sparkColor[accent]}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M2 24 C10 24, 14 14, 22 16 C30 18, 34 8, 42 12 C50 16, 54 4, 62 6 L62 28 L2 28 Z"
            fill={sparkColor[accent]}
            fillOpacity="0.18"
          />
        </svg>
      </div>
    </div>
  );
};
