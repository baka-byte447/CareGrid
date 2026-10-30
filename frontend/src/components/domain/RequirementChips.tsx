import React from 'react';
import { ShieldAlert, Wind } from 'lucide-react';
import { Tooltip } from '@/components/ui/Tooltip';

export interface RequirementChipsProps {
  isolationRequired?: boolean;
  ventilatorRequired?: boolean;
  isolationCapable?: boolean;
  showTooltip?: boolean;
  className?: string;
}

export const RequirementChips: React.FC<RequirementChipsProps> = ({
  isolationRequired,
  ventilatorRequired,
  isolationCapable,
  showTooltip = true,
  className = '',
}) => {
  const safetyNote = 'Display check, not the backend safety layer';

  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`}>
      {isolationRequired && (
        <Tooltip content={showTooltip ? `Requires Negative Pressure Isolation (${safetyNote})` : undefined}>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-pink-500/10 text-pink-700 dark:text-pink-400 border border-pink-500/30">
            <ShieldAlert className="w-3 h-3 text-pink-600 dark:text-pink-400" />
            <span>Isolation</span>
          </span>
        </Tooltip>
      )}

      {isolationCapable && (
        <Tooltip content={showTooltip ? `Negative Pressure Isolation Capable Bed (${safetyNote})` : undefined}>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-700 dark:text-purple-400 border border-purple-500/30">
            <ShieldAlert className="w-3 h-3 text-purple-600 dark:text-purple-400" />
            <span>Iso Capable</span>
          </span>
        </Tooltip>
      )}

      {ventilatorRequired && (
        <Tooltip content={showTooltip ? `Requires Mechanical Ventilation Support (${safetyNote})` : undefined}>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-500/30">
            <Wind className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
            <span>Ventilator</span>
          </span>
        </Tooltip>
      )}
    </div>
  );
};
