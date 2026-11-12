
import React, { useState } from 'react';
import { useMetrics, useBeds, usePatients } from '@/api/hooks';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { MetricCard } from '@/components/domain/MetricCard';
import { AcuityBadge } from '@/components/domain/AcuityBadge';
import { RequirementChips } from '@/components/domain/RequirementChips';
import { MetricGridSkeleton, TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatPct } from '@/lib/format';
import { ACUITY_LABELS, WARD_TYPE_LIST, AcuityLevel } from '@/lib/constants';
import { Patient, Bed } from '@/api/schemas';
import { RecommendationDrawer } from './RecommendationDrawer';

import {
  BedDouble,
  Users,
  Wind,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  Activity,
  HeartPulse,
} from 'lucide-react';

export const CommandCentrePage: React.FC = () => {
  const { user } = useAuth();

  // Permissions
  const canViewMetrics = true;

  const canAllocate =
    user?.role === 'admin' || user?.role === 'doctor';

  // Metrics are restricted to Admin and Operator
  const {
    data: metrics,
    isLoading: metricsLoading,
    error: metricsError,
    refetch: refetchMetrics,
    dataUpdatedAt: metricsUpdatedAt,
  } = useMetrics(30_000, canViewMetrics);

  // Beds are accessible to all roles
  const {
    data: bedsData,
    isLoading: bedsLoading,
    error: bedsError,
    refetch: refetchBeds,
    dataUpdatedAt: bedsUpdatedAt,
  } = useBeds(30_000);

  // Patients are accessible to all roles
  const {
    data: patientsData,
    isLoading: patientsLoading,
    error: patientsError,
    refetch: refetchPatients,
    dataUpdatedAt: patientsUpdatedAt,
  } = usePatients(30_000);

  const [selectedPatient, setSelectedPatient] =
    useState<Patient | null>(null);

  // Only wait for metrics when the current role is permitted to fetch them
  const isLoading =
    bedsLoading ||
    patientsLoading ||
    (canViewMetrics && metricsLoading);

  // Metrics errors should not affect Doctor/Nurse
  const isError =
    bedsError ||
    patientsError ||
    (canViewMetrics ? metricsError : null);

  const dataUpdatedAt = Math.max(
    metricsUpdatedAt,
    bedsUpdatedAt,
    patientsUpdatedAt
  );

  const handleRetryAll = () => {
    void refetchBeds();
    void refetchPatients();

    if (canViewMetrics) {
      void refetchMetrics();
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Hospital Command Centre"
          description="Real-time capacity tracking, triage acuity distribution, and operational alerts."
        />
        <MetricGridSkeleton />
        <TableSkeleton rows={4} />
      </div>
    );
  }

  // Error state for data the current user is authorized to access
  if (isError) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Hospital Command Centre"
          description="Real-time capacity tracking, triage acuity distribution, and operational alerts."
        />
        <ErrorState
          error={bedsError || patientsError || metricsError}
          onRetry={handleRetryAll}
        />
      </div>
    );
  }

  const beds: Bed[] = bedsData || [];
  const patients: Patient[] = patientsData || [];

  // Calculate bed occupancy from permitted bed data
  const bedsTotal = beds.length;

  const bedsOccupied = beds.filter(
    (bed) => bed.status === 'OCCUPIED'
  ).length;

  const bedOccupancyRate =
    bedsTotal > 0 ? bedsOccupied / bedsTotal : 0;

  // Group beds by ward type
  const wardStats = WARD_TYPE_LIST.map((type) => {
    const wardBeds = beds.filter(
      (bed) => bed.bed_type === type
    );

    const total = wardBeds.length;

    const occupied = wardBeds.filter(
      (bed) => bed.status === 'OCCUPIED'
    ).length;

    const available = wardBeds.filter(
      (bed) => bed.status === 'AVAILABLE'
    ).length;

    const rate = total > 0 ? occupied / total : 0;

    return {
      type,
      total,
      occupied,
      available,
      rate,
    };
  });

  // Calculate waiting queue breakdown by acuity
  const waitingPatients = patients.filter(
    (patient) => patient.current_status === 'WAITING'
  );

  const criticalWaiting = waitingPatients.filter(
    (patient) => patient.acuity >= 4
  );

  const acuityCounts: Record<number, number> = {
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
  };

  waitingPatients.forEach((patient) => {
    if (acuityCounts[patient.acuity] !== undefined) {
      acuityCounts[patient.acuity]++;
    }
  });

  // Needs Attention items
  const attentionItems: {
    id: string;
    title: string;
    desc: string;
    severity: 'high' | 'medium';
  }[] = [];

  if (metrics && metrics.ventilators_available <= 1) {
    attentionItems.push({
      id: 'vent-shortage',
      title: 'Ventilator Inventory Critical',
      desc: `Only ${metrics.ventilators_available} ventilator(s) available across hospital.`,
      severity: 'high',
    });
  }

  const icuStat = wardStats.find(
    (ward) => ward.type === 'ICU'
  );

  if (
    icuStat &&
    icuStat.available <= 1 &&
    icuStat.total > 0
  ) {
    attentionItems.push({
      id: 'icu-capacity',
      title: 'ICU Near Capacity',
      desc: `Only ${icuStat.available} of ${icuStat.total} ICU beds available (${formatPct(icuStat.rate)} occupied).`,
      severity: 'high',
    });
  }

  if (criticalWaiting.length > 0) {
    attentionItems.push({
      id: 'critical-queue',
      title: 'High-Acuity Patients in Queue',
      desc: `${criticalWaiting.length} patient(s) with Acuity 4 or 5 are awaiting bed allocation.`,
      severity: 'high',
    });
  }

  return (
    <div className="space-y-6">

      {/* Page Header */}
      <PageHeader
        title="Hospital Command Centre"
        description="Real-time capacity tracking, triage acuity distribution, and operational alerts."
        actions={
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-text-muted">
              Auto-refresh 30s &bull; Last sync:{' '}
              {dataUpdatedAt
                ? new Date(dataUpdatedAt).toLocaleTimeString()
                : '—'}
            </span>

            <Button
              variant="outline"
              size="sm"
              onClick={handleRetryAll}
              leftIcon={
                <RefreshCw className="w-3.5 h-3.5" />
              }
            >
              Sync
            </Button>
          </div>
        }
      />

      {/* Top 4 KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        <MetricCard
          label="Bed Occupancy"
          value={
            metrics
              ? formatPct(metrics.bed_occupancy_rate)
              : formatPct(bedOccupancyRate)
          }
          subtext={
            metrics
              ? `${metrics.beds_occupied} of ${metrics.beds_total} beds occupied`
              : `${bedsOccupied} of ${bedsTotal} beds occupied`
          }
          icon={<BedDouble className="w-5 h-5" />}
          accent={
            (metrics?.bed_occupancy_rate ?? bedOccupancyRate) > 0.85
              ? 'red'
              : 'primary'
          }
        />

        <MetricCard
          label="Admission Queue"
          value={metrics?.patients_waiting ?? waitingPatients.length}
          subtext={`${criticalWaiting.length} high-acuity (L4/L5) pending`}
          icon={<Users className="w-5 h-5" />}
          accent={
            criticalWaiting.length > 0 ? 'amber' : 'purple'
          }
        />

        <MetricCard
          label="Ventilator Fleet"
          value={
            metrics
              ? `${metrics.ventilators_available} / ${metrics.ventilators_total}`
              : '—'
          }
          subtext={
            metrics
              ? `${metrics.ventilators_in_use} in clinical use`
              : 'Metrics unavailable for this role'
          }
          icon={<Wind className="w-5 h-5" />}
          accent={
            metrics && metrics.ventilators_available <= 1
              ? 'red'
              : 'green'
          }
        />

        <MetricCard
          label="Allocations Made"
          value={metrics?.approved_allocations ?? '—'}
          subtext={
            metrics
              ? `${metrics.patients_admitted} total patients admitted`
              : 'Metrics unavailable for this role'
          }
          icon={<CheckCircle className="w-5 h-5" />}
          accent="green"
        />

      </div>

      {/* Needs Attention + Ward Capacity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Needs Attention Panel */}
        <Card className="lg:col-span-1 border-amber-500/20 bg-amber-500/5">
          <CardHeader>
            <div className="flex items-center justify-between">

              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />

                <CardTitle className="text-sm font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200">
                  Needs Attention
                </CardTitle>
              </div>

              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-800 dark:text-amber-300">
                {attentionItems.length}{' '}
                {attentionItems.length === 1 ? 'Alert' : 'Alerts'}
              </span>

            </div>
          </CardHeader>

          <CardContent>
            {attentionItems.length === 0 ? (
              <div className="text-center py-6 text-text-muted text-xs">
                <CheckCircle className="w-8 h-8 mx-auto mb-2 text-emerald-500 opacity-80" />
                No acute capacity or ventilator warnings currently detected.
              </div>
            ) : (
              <div className="space-y-3">
                {attentionItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 rounded-lg bg-bg-surface border border-amber-500/30 text-xs space-y-1 shadow-sm"
                  >
                    <div className="font-semibold text-text-primary flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                      {item.title}
                    </div>

                    <p className="text-text-secondary">
                      {item.desc}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Capacity Breakdown by Ward Type */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary flex items-center gap-2">
              <Activity className="w-4 h-4 text-brand-primary" />
              Ward Capacity Status
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-4">
              {wardStats.map((ward) => (
                <div
                  key={ward.type}
                  className="space-y-1.5"
                >
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-text-primary">
                      {ward.type === 'STEP_DOWN'
                        ? 'Step-Down Unit'
                        : ward.type === 'WARD'
                          ? 'General Ward'
                          : 'Intensive Care Unit (ICU)'}
                    </span>

                    <span className="font-mono text-text-secondary">
                      {ward.available} free / {ward.total} total (
                      {formatPct(ward.rate)})
                    </span>
                  </div>

                  <div className="w-full h-2.5 rounded-full bg-border-light dark:bg-border-medium/30 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        ward.rate > 0.9
                          ? 'bg-red-500'
                          : ward.rate > 0.75
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                      }`}
                      style={{
                        width: `${Math.min(ward.rate * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

      </div>

      {/* Triage Queue Breakdown & Critical Waiting Patients */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Acuity Triage Distribution */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-rose-500" />
              Queue Acuity Distribution
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-2.5">
              {[5, 4, 3, 2, 1].map((acuity) => {
                const count = acuityCounts[acuity] || 0;

                const pct =
                  waitingPatients.length > 0
                    ? (count / waitingPatients.length) * 100
                    : 0;

                return (
                  <div
                    key={acuity}
                    className="flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <AcuityBadge acuity={acuity} />

                      <span className="text-text-secondary font-medium">
                        {ACUITY_LABELS[acuity as AcuityLevel].label}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-text-primary">
                        {count}
                      </span>

                      <span className="text-[11px] text-text-muted w-10 text-right">
                        ({pct.toFixed(0)}%)
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Priority Patients Pending Allocation */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary">
                Urgent Waiting Patients (Acuity 4 & 5)
              </CardTitle>

              <span className="text-xs text-text-muted">
                {criticalWaiting.length} requiring immediate bed
              </span>
            </div>
          </CardHeader>

          <CardContent>
            {criticalWaiting.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-xs">
                No high-acuity patients currently awaiting bed allocation.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border-light text-text-muted uppercase text-left">
                      <th className="pb-2">Patient ID</th>
                      <th className="pb-2">Acuity</th>
                      <th className="pb-2">Specialty</th>
                      <th className="pb-2">Requirements</th>

                      {canAllocate && (
                        <th className="pb-2 text-right">
                          Action
                        </th>
                      )}
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-border-light/60">
                    {criticalWaiting.slice(0, 5).map((patient) => (
                      <tr
                        key={patient.patient_id}
                        className="hover:bg-bg-surface-hover/60"
                      >
                        <td className="py-2.5 font-mono font-semibold text-brand-primary">
                          {patient.patient_id}
                        </td>

                        <td className="py-2.5">
                          <AcuityBadge
                            acuity={patient.acuity}
                            showLabel
                          />
                        </td>

                        <td className="py-2.5 font-medium">
                          {patient.specialty}
                        </td>

                        <td className="py-2.5">
                          <RequirementChips
                            isolationRequired={patient.isolation_required}
                            ventilatorRequired={patient.ventilator_required}
                          />
                        </td>

                        {canAllocate && (
                          <td className="py-2.5 text-right">
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => setSelectedPatient(patient)}
                              rightIcon={
                                <ArrowRight className="w-3 h-3" />
                              }
                            >
                              Allocate
                            </Button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* Recommendation Drawer Modal */}
      {selectedPatient && (
        <RecommendationDrawer
          patient={selectedPatient}
          isOpen={!!selectedPatient}
          onClose={() => setSelectedPatient(null)}
          onSuccess={() => {
            setSelectedPatient(null);
            handleRetryAll();
          }}
        />
      )}

    </div>
  );
};
