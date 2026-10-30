import React from 'react';
import { BedType } from '@/api/schemas';

export interface WardBadgeProps {
  bedType: BedType | string;
  className?: string;
}

export const WardBadge: React.FC<WardBadgeProps> = ({ bedType, className = '' }) => {
  const styles: Record<string, string> = {
    ICU: 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30',
    STEP_DOWN: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30',
    WARD: 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30',
  };

  const label: Record<string, string> = {
    ICU: 'ICU',
    STEP_DOWN: 'Step-Down',
    WARD: 'General Ward',
  };

  const resolvedStyle = styles[bedType] || 'bg-slate-500/10 text-slate-700 dark:text-slate-400 border-slate-500/30';
  const resolvedLabel = label[bedType] || bedType;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${resolvedStyle} ${className}`}
    >
      {resolvedLabel}
    </span>
  );
};
