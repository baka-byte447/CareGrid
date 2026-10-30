import React from 'react';
import { Bed } from '@/api/schemas';
import { BedDouble, Shield } from 'lucide-react';
import { Tooltip } from '@/components/ui/Tooltip';

export interface BedTileProps {
  bed: Bed;
  isSelected?: boolean;
  onClick?: (bed: Bed) => void;
  className?: string;
}

export const BedTile: React.FC<BedTileProps> = ({
  bed,
  isSelected = false,
  onClick,
  className = '',
}) => {
  const isAvailable = bed.status === 'AVAILABLE';

  const statusStyles = isAvailable
    ? 'bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-500/30 hover:border-emerald-500 hover:bg-emerald-500/15'
    : 'bg-red-500/10 text-red-800 dark:text-red-300 border-red-500/30 opacity-80';

  const selectedRing = isSelected ? 'ring-2 ring-brand-primary ring-offset-2' : '';

  return (
    <div
      onClick={() => onClick?.(bed)}
      className={`relative flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all duration-150 cursor-pointer select-none group min-h-[84px] ${statusStyles} ${selectedRing} ${className}`}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.(bed);
        }
      }}
      aria-label={`Bed ${bed.bed_id}, ${bed.status}, Type ${bed.bed_type}, Ward ${bed.ward}`}
    >
      {bed.isolation_capable && (
        <div className="absolute top-1.5 right-1.5">
          <Tooltip content="Isolation Capable (Display check, not the backend safety layer)">
            <Shield className="w-3.5 h-3.5 text-pink-600 dark:text-pink-400" />
          </Tooltip>
        </div>
      )}

      <BedDouble className={`w-5 h-5 mb-1 ${isAvailable ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`} />

      <span className="font-mono text-xs font-bold tracking-tight text-text-primary">
        {bed.bed_id}
      </span>

      <span className="text-[10px] font-medium tracking-wide uppercase opacity-75 mt-0.5">
        {bed.status}
      </span>
    </div>
  );
};
