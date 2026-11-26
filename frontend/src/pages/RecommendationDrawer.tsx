import React, { useState, useEffect, useRef } from 'react';
import { Patient, Bed, RecommendResponse, RecommendationAlgorithm } from '@/api/schemas';
import { useRecommendAllocation, useApproveAllocation, useRejectAllocation, useBeds } from '@/api/hooks';
import { Dialog } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { AcuityBadge } from '@/components/domain/AcuityBadge';
import { RequirementChips } from '@/components/domain/RequirementChips';
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

function approvalFailureMessage(error: Error): string {
  const message = error.message;
  const normalized = message.toLowerCase();

  if (normalized.includes('dqn') && normalized.includes('safety')) {
    return 'DQN safety validation failed. Request a fresh recommendation before trying again.';
  }
  if (normalized.includes('patient') || normalized.includes('encounter')) {
    return 'The patient or admission is no longer eligible. Refresh the patient state and request a new recommendation.';
  }
  if (
    normalized.includes('bed') ||
    normalized.includes('ventilator') ||
    normalized.includes('equipment')
  ) {
    return 'A required resource is no longer available or compatible. Request a new recommendation.';
  }
  if (
    normalized.includes('recommendation has already') ||
    normalized.includes('recommendation has no bed') ||
    normalized.includes('recommendation is not successful') ||
    normalized.includes('recommendation is not linked') ||
    normalized.includes('consumed')
  ) {
    return 'This recommendation expired or was already decided. Request a new recommendation.';
  }
  return message;
}

function rejectionFailureMessage(error: Error): string {
  const message = error.message;
  const normalized = message.toLowerCase();

  if (normalized.includes('already been decided')) {
    return 'This recommendation was already decided. Request a new recommendation.';
  }
  if (normalized.includes('recommendation not found') || normalized.includes('invalid recommendation')) {
    return 'This recommendation could not be found. Request a fresh recommendation.';
  }
  if (
    normalized.includes('not eligible') ||
    normalized.includes('patient') ||
    normalized.includes('encounter')
  ) {
    return 'This recommendation is no longer eligible for rejection. Refresh the patient state and request a new recommendation.';
  }
  return message;
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
  const rejectMutation = useRejectAllocation();

  const [algorithm, setAlgorithm] = useState<RecommendationAlgorithm>('rule_based');
  const [recommendationSnapshot, setRecommendationSnapshot] = useState<RecommendationSnapshot | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [isRecommending, setIsRecommending] = useState(false);
  const recommendationRequestId = useRef(0);
  const decisionInFlightRef = useRef(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rejectError, setRejectError] = useState<string | null>(null);
  const [rejectSuccess, setRejectSuccess] = useState<string | null>(null);

  const requestRecommendation = (requestedAlgorithm: RecommendationAlgorithm) => {
    const requestId = ++recommendationRequestId.current;
    setRecommendationSnapshot(null);
    setRecommendationError(null);
    setIsRecommending(true);
    setApproveError(null);
    setRejectionReason('');
    setRejectError(null);
    setRejectSuccess(null);

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
  const isRejecting = rejectMutation.isPending;
  const isDecisionPending = isApproving || isRejecting;

  // Find recommended bed details if present
  const beds: Bed[] = bedsData || [];
  const recommendedBed: Bed | undefined = beds.find(
    (b: Bed) => b.bed_id === recommendation?.recommended_bed_id
  );

  const handleApprove = async () => {
    if (
      decisionInFlightRef.current ||
      !recommendation?.recommendation_id ||
      !recommendation.recommended_bed_id ||
      recommendation.status !== 'RECOMMENDED' ||
      isDecisionPending ||
      rejectSuccess
    ) return;
    decisionInFlightRef.current = true;
    setApproveError(null);
    setRejectError(null);

    approveMutation.mutate(
      { recommendation_id: recommendation.recommendation_id },
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
          const message = approvalFailureMessage(err);
          setApproveError(message);
          showToast({
            type: 'error',
            title: 'Allocation Failed',
            message,
          });
        },
        onSettled: () => {
          decisionInFlightRef.current = false;
        },
      }
    );
  };

  const isRejectable = Boolean(
    recommendation &&
    recommendation.recommendation_id > 0 &&
    recommendation.patient_id === patient.patient_id &&
    patient.current_status === 'WAITING' &&
    recommendation.status === 'RECOMMENDED' &&
    recommendation.recommended_bed_id
  );
  const hasValidRejectionReason = rejectionReason.trim().length >= 3;

  const handleReject = () => {
    if (
      decisionInFlightRef.current ||
      !isRejectable ||
      !recommendation ||
      !hasValidRejectionReason ||
      isDecisionPending ||
      rejectSuccess
    ) return;

    decisionInFlightRef.current = true;
    setRejectError(null);
    setApproveError(null);
    rejectMutation.mutate(
      {
        recommendation_id: recommendation.recommendation_id,
        reason: rejectionReason.trim(),
      },
      {
        onSuccess: (data) => {
          const message = `Recommendation #${data.recommendation_id} rejected.`;
          setRejectSuccess(message);
          showToast({ type: 'success', title: 'Recommendation Rejected', message });
        },
        onError: (error: Error) => {
          const message = rejectionFailureMessage(error);
          setRejectError(message);
          showToast({ type: 'error', title: 'Rejection Failed', message });
        },
        onSettled: () => {
          decisionInFlightRef.current = false;
        },
      },
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
          <Button
            variant="danger"
            size="sm"
            onClick={handleReject}
            isLoading={isRejecting}
            disabled={
              !isRejectable ||
              !hasValidRejectionReason ||
              isRecommending ||
              isDecisionPending ||
              Boolean(rejectSuccess)
            }
          >
            Reject Recommendation
          </Button>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} disabled={isDecisionPending}>
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
                !recommendation?.recommendation_id ||
                !recommendation?.recommended_bed_id ||
                isDecisionPending ||
                Boolean(rejectSuccess)
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

        <div className="p-3.5 rounded-xl border border-brand-primary/30 bg-brand-primary/5 space-y-2">
          <div className="flex items-center justify-between">
            <label htmlFor="recommendation-algorithm" className="block text-xs font-semibold text-text-primary">
              Allocation Policy Engine
            </label>
            <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              {algorithm === 'dqn_safe' ? 'Deep RL + Guardrails' : 'Heuristic Rules'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 p-1 rounded-lg bg-bg-surface border border-border-light">
            <button
              type="button"
              disabled={isDecisionPending}
              onClick={() => {
                if (algorithm !== 'rule_based') {
                  setAlgorithm('rule_based');
                  requestRecommendation('rule_based');
                }
              }}
              className={`py-2 px-3 rounded-md text-xs font-semibold transition-all ${
                algorithm === 'rule_based'
                  ? 'bg-brand-primary text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover'
              }`}
            >
              Rule-Based
            </button>
            <button
              type="button"
              disabled={isDecisionPending}
              onClick={() => {
                if (algorithm !== 'dqn_safe') {
                  setAlgorithm('dqn_safe');
                  requestRecommendation('dqn_safe');
                }
              }}
              className={`py-2 px-3 rounded-md text-xs font-semibold transition-all ${
                algorithm === 'dqn_safe'
                  ? 'bg-brand-primary text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover'
              }`}
            >
              DQN Safe (RL)
            </button>
          </div>
          {/* Hidden accessible select preserved for screen-readers/tests */}
          <select
            id="recommendation-algorithm"
            aria-label="Recommendation algorithm"
            value={algorithm}
            disabled={isDecisionPending}
            onChange={(event) => {
              const selected = event.target.value as RecommendationAlgorithm;
              setAlgorithm(selected);
              requestRecommendation(selected);
            }}
            className="sr-only"
          >
            <option value="rule_based">Rule-Based</option>
            <option value="dqn_safe">DQN Safe</option>
          </select>
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
            {recommendation.explanation && (
              <section className="rounded-xl border p-4 space-y-2">
                <h3 className="font-semibold">Clinical Rationale &amp; Counterfactual</h3>
                <p>{recommendation.explanation.summary} {recommendation.explanation.chosen_reason}</p>
                <p>{recommendation.explanation.counterfactual}</p>
                <p>{recommendation.explanation.safety_guarantee}</p>
                {recommendation.explanation.confidence_margin != null && (
                  <p>Q-value difference: {recommendation.explanation.confidence_margin.toFixed(3)}</p>
                )}
              </section>
            )}
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
                  <span>
                    Recommendation #{recommendation.recommendation_id}
                    <span>Generated by: {algorithmLabel(recommendation.algorithm)}</span>
                  </span>
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
                    Recommendation #{recommendation.recommendation_id}
                    <span>Generated by: {algorithmLabel(recommendation.algorithm)}</span>
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
              <div className="p-4 rounded-xl border border-indigo-500/25 bg-indigo-500/5 space-y-3 animate-fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-semibold text-text-primary">
                    <Info className="w-4 h-4 text-indigo-500" />
                    <span>DQN Safe decision details</span>
                  </div>
                  {recommendation.los_estimate_days != null && (
                    <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-700 dark:text-indigo-300">
                      {recommendation.los_estimate_days.toFixed(1)} days
                    </span>
                  )}
                </div>

                {recommendation.safety?.overridden && (
                  <div className="p-3 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
                    <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <div className="space-y-0.5 text-[11px]">
                      <div className="font-bold">
                        Safety Override: {actionLabel(recommendation.proposed_action, recommendation.proposed_bed_type)} &rarr; {actionLabel(recommendation.final_action, recommendation.final_bed_type)}
                      </div>
                      {recommendation.safety.rule_triggered && (
                        <div className="font-mono text-[10px] uppercase tracking-wide opacity-90">
                          Rule: {recommendation.safety.rule_triggered.replace(/_/g, ' ')}
                        </div>
                      )}
                      {recommendation.safety.reason && (
                        <div className="opacity-90">
                          {recommendation.safety.reason.replace(/_/g, ' ')}
                        </div>
                      )}
                    </div>
                  </div>
                )}

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
                </div>

                <div>
                  <span className="block text-[11px] font-semibold text-text-muted mb-2">
                    Action Q-Values
                  </span>
                  {recommendation.q_values?.length ? (() => {
                    const qVals = recommendation.q_values;
                    const minQ = Math.min(...qVals);
                    const maxQ = Math.max(...qVals);
                    const span = maxQ - minQ || 1;
                    return (
                      <div className="space-y-2">
                        {qVals.map((value, index) => {
                          const pct = Math.max(8, Math.round(((value - minQ) / span) * 100));
                          const isFinal = recommendation.final_action === index;
                          return (
                            <div key={`${index}-${value}`} className="space-y-1">
                              <div className="flex justify-between text-[11px]">
                                <span className={isFinal ? 'font-bold text-brand-primary' : 'text-text-secondary'}>
                                  {actionLabel(index, null)} {isFinal ? '(Selected)' : ''}
                                </span>
                                <span className="font-mono font-semibold text-text-primary">
                                  {value.toFixed(4)}
                                </span>
                              </div>
                              <div className="w-full h-2 rounded-full bg-bg-surface border border-border-light overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-300 ${
                                    isFinal ? 'bg-brand-primary' : 'bg-indigo-400/60'
                                  }`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })() : (
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
            <div className="mt-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => requestRecommendation(algorithm)}
                disabled={isRecommending || isDecisionPending}
              >
                Request new recommendation
              </Button>
            </div>
          </div>
        )}

        {recommendation && (
          <div className="space-y-2">
            <label htmlFor="recommendation-rejection-reason" className="block text-xs font-semibold text-text-primary">
              Rejection reason
            </label>
            <textarea
              id="recommendation-rejection-reason"
              aria-label="Rejection reason"
              rows={3}
              value={rejectionReason}
              onChange={(event) => {
                setRejectionReason(event.target.value);
                setRejectError(null);
              }}
              disabled={!isRejectable || isDecisionPending || Boolean(rejectSuccess)}
              placeholder="Enter the clinical reason for rejecting this recommendation"
              className="w-full rounded-md border border-border-medium bg-bg-surface px-3 py-2 text-sm text-text-primary focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary disabled:opacity-60"
            />
            {isRejectable && !hasValidRejectionReason && !rejectSuccess && (
              <p className="text-[11px] text-text-muted">Enter at least 3 non-space characters to enable rejection.</p>
            )}
          </div>
        )}

        {rejectError && (
          <div role="alert" className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 text-xs">
            <strong>Rejection error: </strong>
            <span>{rejectError}</span>
          </div>
        )}
        {rejectSuccess && (
          <div role="status" className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 text-xs">
            {rejectSuccess} The original recommendation details remain available above.
          </div>
        )}
      </div>
    </Dialog>
  );
};
