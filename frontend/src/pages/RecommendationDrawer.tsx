import React, { useState, useEffect, useRef } from 'react';
import { Patient, Bed, RecommendResponse, RecommendationAlgorithm } from '@/api/schemas';
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

interface RecommendationSnapshot {
  patientId: string;
  requestedAlgorithm: RecommendationAlgorithm;
  data: RecommendResponse;
}

function algorithmLabel(algorithm: string): string {
  if (algorithm === 'dqn_safe') return 'DQN Safe';
  if (algorithm === 'rule_based') return 'Rule-Based';
  if (algorithm === 'rule_based_fallback') return 'Rule-Based fallback';
  return algorithm;
}

function actionLabel(action: number | null | undefined, bedType: string | null | undefined): string {
  if (bedType) return bedType === 'STEP_DOWN' ? 'Step-down' : bedType;
  if (action == null) return 'Not provided';
  return ['ICU', 'Step-down', 'Ward', 'Wait'][action] ?? `Action ${action}`;
}

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

  const [algorithm, setAlgorithm] = useState<RecommendationAlgorithm>('rule_based');
  const [recommendationSnapshot, setRecommendationSnapshot] = useState<RecommendationSnapshot | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [isRecommending, setIsRecommending] = useState(false);
  const recommendationRequestId = useRef(0);
  const [approveError, setApproveError] = useState<string | null>(null);

  const requestRecommendation = (requestedAlgorithm: RecommendationAlgorithm) => {
    const requestId = ++recommendationRequestId.current;
    setRecommendationSnapshot(null);
    setRecommendationError(null);
    setIsRecommending(true);
    setApproveError(null);

    recommendMutation.mutate(
      { patient_id: patient.patient_id, algorithm: requestedAlgorithm },
      {
        onSuccess: (data) => {
          if (recommendationRequestId.current === requestId) {
            setRecommendationSnapshot({
              patientId: patient.patient_id,
              requestedAlgorithm,
              data,
            });
          }
        },
        onError: (error: Error) => {
          if (recommendationRequestId.current === requestId) {
            setRecommendationError(error.message);
          }
        },
        onSettled: () => {
          if (recommendationRequestId.current === requestId) {
            setIsRecommending(false);
          }
        },
      },
    );
  };

  // Every open/new patient begins with the existing Rule-Based behavior.
  useEffect(() => {
    if (!isOpen) {
      recommendationRequestId.current += 1;
      return;
    }

    setAlgorithm('rule_based');
    requestRecommendation('rule_based');
    return () => {
      recommendationRequestId.current += 1;
    };
  }, [isOpen, patient.patient_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const recommendation =
    recommendationSnapshot?.patientId === patient.patient_id &&
    recommendationSnapshot.requestedAlgorithm === algorithm
      ? recommendationSnapshot.data
      : undefined;
  const isApproving = approveMutation.isPending;

  // Find recommended bed details if present
  const beds: Bed[] = bedsData || [];
  const recommendedBed: Bed | undefined = beds.find(
    (b: Bed) => b.bed_id === recommendation?.recommended_bed_id
  );

  const handleApprove = async () => {
    if (algorithm === 'dqn_safe' || !recommendation?.recommended_bed_id) return;
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

  const isNoSuitableBed = Boolean(
    recommendation &&
    (recommendation.status !== 'RECOMMENDED' || !recommendation.recommended_bed_id)
  );

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
            <Tooltip
              content={
                algorithm === 'dqn_safe'
                  ? 'DQN Safe approval is unavailable because the backend approval endpoint does not bind approval to the DQN recommendation.'
                  : ''
              }
            >
              <div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleApprove}
                  isLoading={isApproving}
                  disabled={
                    algorithm === 'dqn_safe' ||
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
            </Tooltip>
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

        <div className="p-3 rounded-xl border border-brand-primary/30 bg-brand-primary/5 space-y-1.5">
          <label htmlFor="recommendation-algorithm" className="block text-xs font-semibold text-text-primary">
            Recommendation algorithm
          </label>
          <select
            id="recommendation-algorithm"
            aria-label="Recommendation algorithm"
            value={algorithm}
            disabled={isApproving}
            onChange={(event) => {
              const selected = event.target.value as RecommendationAlgorithm;
              setAlgorithm(selected);
              requestRecommendation(selected);
            }}
            className="w-full rounded-md border border-border-medium bg-bg-surface px-3 py-2 text-sm text-text-primary focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary disabled:opacity-60"
          >
            <option value="rule_based">Rule-Based</option>
            <option value="dqn_safe">DQN Safe</option>
          </select>
          {algorithm === 'dqn_safe' && (
            <p className="text-[11px] text-amber-700 dark:text-amber-300">
              Approval is disabled for DQN Safe until the backend can bind and audit approval against this decision.
            </p>
          )}
        </div>

        {/* AI Recommendation State */}
        {isRecommending && (
          <div className="flex flex-col items-center justify-center p-8 bg-sky-500/5 border border-sky-500/20 rounded-xl gap-2 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand-primary" />
            <p className="font-semibold text-text-primary">
              Loading {algorithmLabel(algorithm)} recommendation...
            </p>
            <p className="text-text-muted text-[11px]">
              Evaluating hospital capacity, predicted LOS, and clinical safety constraints.
            </p>
          </div>
        )}

        {recommendationError && !isRecommending && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 space-y-2">
            <div className="flex items-center gap-2 font-bold">
              <AlertOctagon className="w-4 h-4 flex-shrink-0" />
              <span>Failed to fetch recommendation</span>
            </div>
            <p className="text-[11px] font-mono">{recommendationError}</p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => requestRecommendation(algorithm)}
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
                  <span>
                    {recommendation.status === 'WAIT'
                      ? 'The selected policy recommends waiting'
                      : 'No Suitable Bed Available'}
                  </span>
                </div>
                <p className="text-text-secondary leading-relaxed">{recommendation.reason}</p>
                <div className="pt-2 text-[11px] text-text-muted flex items-center gap-2">
                  <Cpu className="w-3.5 h-3.5" />
                  <span>Generated by: {algorithmLabel(recommendation.algorithm)}</span>
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
                    Generated by: {algorithmLabel(recommendation.algorithm)}
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

                {/* Existing rule-based display checks; these are not the backend DQN safety layer. */}
                <div className="pt-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-text-muted mb-1.5">
                    <Info className="w-3 h-3" />
                    <span>Clinical requirement display checks</span>
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

            {algorithm === 'dqn_safe' && (
              <div className="p-4 rounded-xl border border-indigo-500/25 bg-indigo-500/5 space-y-3">
                <div className="flex items-center gap-2 font-semibold text-text-primary">
                  <Info className="w-4 h-4 text-indigo-500" />
                  <span>DQN Safe decision details</span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-[11px]">
                  <div>
                    <span className="block text-text-muted">Safety review</span>
                    <span className="font-semibold text-text-primary">
                      {!recommendation.safety
                        ? 'Safety information unavailable'
                        : recommendation.safety.overridden
                          ? 'Safety intervention applied'
                          : 'No safety intervention reported'}
                    </span>
                  </div>
                  <div>
                    <span className="block text-text-muted">Action reviewed</span>
                    <span className="font-semibold text-text-primary">
                      {recommendation.safety
                        ? actionLabel(recommendation.safety.original_action, null)
                        : 'Not provided'}
                    </span>
                  </div>
                  {recommendation.safety?.rule_triggered && (
                    <div className="col-span-2">
                      <span className="block text-text-muted">Safety rule</span>
                      <span className="font-semibold text-text-primary">
                        {recommendation.safety.rule_triggered.replace(/_/g, ' ')}
                      </span>
                    </div>
                  )}
                  {recommendation.safety?.reason && (
                    <div className="col-span-2">
                      <span className="block text-text-muted">Safety reason</span>
                      <span className="text-text-secondary">
                        {recommendation.safety.reason.replace(/_/g, ' ')}
                      </span>
                    </div>
                  )}
                  <div>
                    <span className="block text-text-muted">Proposed action</span>
                    <span className="font-semibold text-text-primary">
                      {actionLabel(recommendation.proposed_action, recommendation.proposed_bed_type)}
                    </span>
                  </div>
                  <div>
                    <span className="block text-text-muted">Final action</span>
                    <span className="font-semibold text-text-primary">
                      {actionLabel(recommendation.final_action, recommendation.final_bed_type)}
                    </span>
                  </div>
                  <div>
                    <span className="block text-text-muted">Proposed bed type</span>
                    <span className="font-semibold text-text-primary">
                      {recommendation.proposed_bed_type ?? 'Not provided'}
                    </span>
                  </div>
                  <div>
                    <span className="block text-text-muted">Final bed type</span>
                    <span className="font-semibold text-text-primary">
                      {recommendation.final_bed_type ?? 'Not provided'}
                    </span>
                  </div>
                  <div>
                    <span className="block text-text-muted">Estimated length of stay</span>
                    <span className="font-semibold text-text-primary">
                      {recommendation.los_estimate_days == null
                        ? 'Not provided'
                        : `${recommendation.los_estimate_days.toFixed(1)} days`}
                    </span>
                  </div>
                </div>

                <div>
                  <span className="block text-[11px] text-text-muted mb-1">Q-values by action</span>
                  {recommendation.q_values?.length ? (
                    <ul className="grid grid-cols-2 gap-1 text-[11px]">
                      {recommendation.q_values.map((value, index) => (
                        <li key={`${index}-${value}`} className="flex justify-between rounded bg-bg-surface px-2 py-1">
                          <span>{actionLabel(index, null)}</span>
                          <span className="font-mono">{value.toFixed(4)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[11px] text-text-secondary">Q-values not provided.</p>
                  )}
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
