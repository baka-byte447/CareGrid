import React from 'react';
import { Patient } from '@/api/schemas';
import { AcuityBadge } from '@/components/domain/AcuityBadge';
import { RequirementChips } from '@/components/domain/RequirementChips';
import { StatusDot } from '@/components/domain/StatusDot';
import { formatSimulatedDate, formatLOS } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { ChevronRight, ArrowLeftRight, LogOut } from 'lucide-react';

export interface PatientRowProps {
  patient: Patient;
  onSelect?: (patient: Patient) => void;
  onDischarge?: (patient: Patient) => void;
  onTransfer?: (patient: Patient) => void;
  canAllocate?: boolean;
  canManageAdmitted?: boolean;
  isSelected?: boolean;
}

export const PatientRow: React.FC<PatientRowProps> = ({
  patient,
  onSelect,
  onDischarge,
  onTransfer,
  canAllocate = true,
  canManageAdmitted = false,
  isSelected = false,
}) => {
  const isWaiting = patient.current_status === 'WAITING';
  const isAdmitted = patient.current_status === 'ADMITTED';
  const isDischarged = patient.current_status === 'DISCHARGED';

  return (
    <tr
      onClick={() => isWaiting && canAllocate && onSelect?.(patient)}
      className={`transition-colors border-b border-border-light hover:bg-bg-surface-hover/80 ${
        isWaiting && canAllocate ? 'cursor-pointer' : ''
      } ${
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
        {patient.current_status === 'WAITING' ? '—' : formatLOS(patient.predicted_los)}
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
          <span
            className={
              isWaiting
                ? 'text-purple-600 dark:text-purple-400 font-semibold'
                : isDischarged
                  ? 'text-slate-500 dark:text-slate-400 font-medium'
                  : 'text-emerald-600 dark:text-emerald-400 font-semibold'
            }
          >
            {patient.current_status}
          </span>
        </span>
      </td>

      <td className="p-3.5 text-right">
        {isWaiting ? (
          canAllocate ? (
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
            <span className="text-xs text-text-muted italic">Awaiting Doctor</span>
          )
        ) : isAdmitted ? (
          canManageAdmitted ? (
            <div className="inline-flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onTransfer?.(patient)}
                leftIcon={<ArrowLeftRight className="w-3 h-3" />}
              >
                Transfer
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onDischarge?.(patient)}
                leftIcon={<LogOut className="w-3 h-3" />}
              >
                Discharge
              </Button>
            </div>
          ) : (
            <span className="text-xs text-text-muted italic">Admitted</span>
          )
        ) : (
          <span className="text-xs text-text-muted italic">Discharged</span>
        )}
      </td>
    </tr>
  );
};
