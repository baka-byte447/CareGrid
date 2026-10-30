import React from 'react';
import { ACUITY_LABELS, AcuityLevel } from '@/lib/constants';

export interface AcuityBadgeProps {
  acuity: number;
  showLabel?: boolean;
  className?: string;
}

export const AcuityBadge: React.FC<AcuityBadgeProps> = ({
  acuity,
  showLabel = false,
  className = '',
}) => {
  const level = (acuity in ACUITY_LABELS ? acuity : 1) as AcuityLevel;
  const config = ACUITY_LABELS[level];

  const colorStyles: Record<AcuityLevel, string> = {
    1: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
    2: 'bg-lime-500/10 text-lime-700 dark:text-lime-400 border-lime-500/30',
    3: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30',
    4: 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/30',
    5: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/40 font-bold animate-pulse',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold border ${colorStyles[level]} ${className}`}
      title={`Acuity Level ${level}: ${config.label} (${config.description})`}
    >
      <span className="font-mono">L{level}</span>
      {showLabel && <span className="font-medium text-[11px]">{config.label}</span>}
    </span>
  );
};
