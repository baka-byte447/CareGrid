import React, { useState, useEffect } from 'react';
import { Patient, Bed } from '@/api/schemas';
import { useRecommendAllocation, useApproveAllocation, useBeds } from '@/api/hooks';
import { Dialog } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { AcuityBadge } from '@/components/domain/AcuityBadge';
import { RequirementChips } from '@/components/domain/RequirementChips';
import { Tooltip } from '@/components/ui/Tooltip';
import { useToast } from '@/components/feedback/Toast';
import { formatLOS, formatSimulatedDate } from '@/lib/format';
import {
  BedDouble,
  Cpu,
  CheckCircle2,
  AlertOctagon,
  ShieldAlert,
  Loader2,
  Info,
} from 'lucide-react';

export interface RecommendationDrawerProps {
  patient: Patient;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const RecommendationDrawer: React.FC<RecommendationDrawerProps> = ({
  patient,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { showToast } = useToast();
  const { data: bedsData } = useBeds();
  const recommendMutation = useRecommendAllocation();
  const approveMutation = useApproveAllocation();

  const [approveError, setApproveError] = useState<string | null>(null);

  // Trigger recommendation query whenever drawer opens for a new patient
  useEffect(() => {
    if (isOpen && patient) {
      setApproveError(null);
      recommendMutation.mutate({ patient_id: patient.patient_id });
    }
  }, [isOpen, patient.patient_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const recommendation = recommendMutation.data;
  const isRecommending = recommendMutation.isPending;
  const isApproving = approveMutation.isPending;

  // Find recommended bed details if present
  const beds: Bed[] = bedsData || [];
  const recommendedBed: Bed | undefined = beds.find(
    (b: Bed) => b.bed_id === recommendation?.recommended_bed_id
  );

  const handleApprove = async () => {
    if (!recommendation?.recommended_bed_id) return;
    setApproveError(null);

    approveMutation.mutate(
      {
        patient_id: patient.patient_id,
        bed_id: recommendation.recommended_bed_id,
      },
      {
        onSuccess: (data) => {
          showToast({
            type: 'success',
            title: 'Bed Allocation Approved',
            message: `Patient ${data.patient_id} successfully allocated to Bed ${data.bed_id}.`,
          });
          onSuccess?.();
          onClose();
        },
        onError: (err: Error) => {
          setApproveError(err.message);
          showToast({
            type: 'error',
            title: 'Allocation Failed',
            message: err.message,
          });
        },
      }
    );
  };

  const isNoSuitableBed =
    recommendation?.status === 'NO_SUITABLE_BED' ||
    recommendation?.recommended_bed_id === null;

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Bed Allocation Decision"
      description={`Clinical admission recommendation for Patient ${patient.patient_id}`}
      maxWidth="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          {/* Tooltip on Reject per prompt requirements */}
          <Tooltip content="Reject is not available in the backend yet">
            <div>
              <Button variant="outline" size="sm" disabled>
                Reject Recommendation
              </Button>
            </div>
          </Tooltip>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} disabled={isApproving}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleApprove}
              isLoading={isApproving}
              disabled={
                isRecommending ||
                isNoSuitableBed ||
                !recommendation?.recommended_bed_id ||
                isApproving
              }
              leftIcon={<CheckCircle2 className="w-4 h-4" />}
            >
              Approve Allocation
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-5 text-text-primary text-xs">
        {/* Patient Summary Card */}
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface-hover/60 space-y-3">
          <div className="flex items-center justify-between border-b border-border-light pb-2">
            <div>
              <span className="font-mono text-sm font-bold text-brand-primary">
                {patient.patient_id}
              </span>
              <span className="text-text-muted ml-2">({patient.age_group})</span>
            </div>
            <AcuityBadge acuity={patient.acuity} showLabel />
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-text-muted block text-[11px]">Specialty</span>
              <span className="font-semibold text-text-primary">{patient.specialty}</span>
            </div>
            <div>
              <span className="text-text-muted block text-[11px]">Predicted LOS</span>
              <span className="font-mono font-semibold text-text-primary">
                {formatLOS(patient.predicted_los)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block text-[11px]">Arrival Time</span>
              <span className="text-text-secondary">
                {formatSimulatedDate(patient.arrival_time)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block text-[11px]">Clinical Demands</span>
              <RequirementChips
                isolationRequired={patient.isolation_required}
                ventilatorRequired={patient.ventilator_required}
              />
            </div>
          </div>
        </div>

        {/* AI Recommendation State */}
        {isRecommending && (
          <div className="flex flex-col items-center justify-center p-8 bg-sky-500/5 border border-sky-500/20 rounded-xl gap-2 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand-primary" />
            <p className="font-semibold text-text-primary">Querying RL Allocation Policy...</p>
            <p className="text-text-muted text-[11px]">
              Evaluating hospital capacity, predicted LOS, and clinical safety constraints.
            </p>
          </div>
        )}

        {recommendMutation.isError && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 space-y-2">
            <div className="flex items-center gap-2 font-bold">
              <AlertOctagon className="w-4 h-4 flex-shrink-0" />
              <span>Failed to fetch recommendation</span>
            </div>
            <p className="text-[11px] font-mono">{recommendMutation.error?.message}</p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => recommendMutation.mutate({ patient_id: patient.patient_id })}
            >
              Retry
            </Button>
          </div>
        )}

        {recommendation && !isRecommending && (
          <div className="space-y-4">
            {isNoSuitableBed ? (
              <div className="p-5 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
                <div className="flex items-center gap-2 font-bold text-amber-800 dark:text-amber-300">
                  <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-600" />
                  <span>No Suitable Bed Available</span>
                </div>
                <p className="text-text-secondary leading-relaxed">{recommendation.reason}</p>
                <div className="pt-2 text-[11px] text-text-muted flex items-center gap-2">
                  <Cpu className="w-3.5 h-3.5" />
                  <span>Algorithm: {recommendation.algorithm}</span>
                </div>
              </div>
            ) : (
              <div className="p-5 rounded-xl bg-brand-primary-light/40 dark:bg-brand-primary/10 border border-brand-primary/30 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-brand-primary flex items-center gap-1.5">
                    <BedDouble className="w-4 h-4" />
                    Recommended Bed
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-bg-surface text-text-secondary border border-border-light flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-brand-primary" />
                    {recommendation.algorithm}
                  </span>
                </div>

                <div className="flex items-baseline gap-3">
                  <span className="text-2xl font-bold font-mono text-text-primary">
                    Bed {recommendation.recommended_bed_id}
                  </span>
                  {recommendedBed && (
                    <span className="text-xs text-text-secondary">
                      ({recommendedBed.ward} &bull; {recommendedBed.bed_type})
                    </span>
                  )}
                </div>

                <p className="text-xs text-text-secondary leading-relaxed bg-bg-surface/80 p-3 rounded-lg border border-border-light/80">
                  {recommendation.reason}
                </p>

                {/* Clinical Safety Checks (Labelled per requirements) */}
                <div className="pt-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-text-muted mb-1.5">
                    <Info className="w-3 h-3" />
                    <span>Display Check (Display check, not the backend safety layer)</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="p-2 rounded bg-bg-surface border border-border-light flex items-center justify-between">
                      <span>Isolation Compatibility:</span>
                      {patient.isolation_required ? (
                        recommendedBed?.isolation_capable ? (
                          <span className="text-emerald-600 font-semibold">Matched</span>
                        ) : (
                          <span className="text-red-600 font-semibold">Requires Caution</span>
                        )
                      ) : (
                        <span className="text-text-muted">Not Required</span>
                      )}
                    </div>
                    <div className="p-2 rounded bg-bg-surface border border-border-light flex items-center justify-between">
                      <span>Ventilator Support:</span>
                      {patient.ventilator_required ? (
                        <span className="text-indigo-600 font-semibold">Required</span>
                      ) : (
                        <span className="text-text-muted">Not Required</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Approval Error Display */}
        {approveError && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 text-xs">
            <strong>Allocation error: </strong>
            <span>{approveError}</span>
          </div>
        )}
      </div>
    </Dialog>
  );
};
