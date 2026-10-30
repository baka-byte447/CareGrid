import React from 'react';
import { Patient } from '@/api/schemas';
import { AcuityBadge } from '@/components/domain/AcuityBadge';
import { RequirementChips } from '@/components/domain/RequirementChips';
import { StatusDot } from '@/components/domain/StatusDot';
import { formatSimulatedDate, formatLOS } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { ChevronRight } from 'lucide-react';

export interface PatientRowProps {
  patient: Patient;
  onSelect?: (patient: Patient) => void;
  isSelected?: boolean;
}

export const PatientRow: React.FC<PatientRowProps> = ({
  patient,
  onSelect,
  isSelected = false,
}) => {
  const isWaiting = patient.current_status === 'WAITING';

  return (
    <tr
      onClick={() => onSelect?.(patient)}
      className={`transition-colors cursor-pointer border-b border-border-light hover:bg-bg-surface-hover/80 ${
        isSelected ? 'bg-brand-primary-light/40 dark:bg-brand-primary/10' : ''
      }`}
    >
      <td className="p-3.5 font-mono text-xs font-bold text-brand-primary">
        {patient.patient_id}
      </td>

      <td className="p-3.5 text-xs text-text-primary">
        {patient.age_group}
      </td>

      <td className="p-3.5">
        <AcuityBadge acuity={patient.acuity} showLabel />
      </td>

      <td className="p-3.5 text-xs font-medium text-text-primary">
        {patient.specialty}
      </td>

      <td className="p-3.5 text-xs font-mono text-text-secondary">
        {formatLOS(patient.predicted_los)}
      </td>

      <td className="p-3.5">
        <RequirementChips
          isolationRequired={patient.isolation_required}
          ventilatorRequired={patient.ventilator_required}
        />
      </td>

      <td className="p-3.5 text-xs text-text-muted whitespace-nowrap">
        {formatSimulatedDate(patient.arrival_time)}
      </td>

      <td className="p-3.5">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium">
          <StatusDot status={patient.current_status} pulse={isWaiting} />
          <span className={isWaiting ? 'text-purple-600 dark:text-purple-400 font-semibold' : 'text-emerald-600 dark:text-emerald-400'}>
            {patient.current_status}
          </span>
        </span>
      </td>

      <td className="p-3.5 text-right">
        {isWaiting ? (
          <Button
            size="sm"
            variant="primary"
            onClick={(e) => {
              e.stopPropagation();
              onSelect?.(patient);
            }}
            rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
          >
            Allocate Bed
          </Button>
        ) : (
          <span className="text-xs text-text-muted italic">Admitted</span>
        )}
      </td>
    </tr>
  );
};
