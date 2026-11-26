
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMetrics, useBeds, usePatients, useAudit, useCompleteBedCleaning, getErrorMessage } from '@/api/hooks';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { MetricCard } from '@/components/domain/MetricCard';
import { AcuityBadge } from '@/components/domain/AcuityBadge';
import { RequirementChips } from '@/components/domain/RequirementChips';
import { WardBadge } from '@/components/domain/WardBadge';
import { MetricGridSkeleton, TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { useToast } from '@/components/feedback/Toast';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatPct, formatServerTimestamp } from '@/lib/format';
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
  Sparkles,
  Zap,
  BarChart3,
  ScrollText,
  UserPlus,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
} from 'recharts';

export const CommandCentrePage: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const cleanBedMutation = useCompleteBedCleaning();

  // Permissions
  const canViewMetrics = true;

  const canAllocate =
    user?.role === 'admin' || user?.role === 'doctor';

  const canCompleteCleaning =
    user?.role === 'admin' || user?.role === 'nurse' || user?.role === 'operator';

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

  const { data: auditData } = useAudit();
  const auditEntries = auditData || [];

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

  const cleaningBeds = beds.filter((bed) => bed.status === 'CLEANING');

  const handleCompleteCleaning = (bedId: string) => {
    cleanBedMutation.mutate(bedId, {
      onSuccess: () => {
        showToast({
          type: 'success',
          title: 'Bed Ready',
          message: `Bed ${bedId} marked clean and is now AVAILABLE.`,
        });
      },
      onError: (err) => {
        showToast({
          type: 'error',
          title: 'Cleaning Update Failed',
          message: getErrorMessage(err),
        });
      },
    });
  };

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Editorial Command Header */}
      <div className="glass-panel border border-border-light rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live &bull; Synced{' '}
              {dataUpdatedAt
                ? new Date(dataUpdatedAt).toLocaleTimeString()
                : '—'}
            </span>
            <span className="text-xs text-text-muted capitalize">
              Signed in as {user?.username ?? 'Clinician'}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Hospital Command Centre
          </h1>
          <p className="text-xs text-text-muted">
            Real-time bed capacity, triage queue prioritization, and clinical resource telemetry.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-center">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetryAll}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Sync Data
          </Button>
          {(user?.role === 'admin' || user?.role === 'doctor' || user?.role === 'nurse') && (
            <Link to="/queue">
              <Button
                variant="primary"
                size="sm"
                leftIcon={<UserPlus className="w-3.5 h-3.5" />}
              >
                New Intake
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Top 4 KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        <MetricCard
          className="animate-slide-up stagger-1"
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

      {/* Clinical Alerts Strip */}
      {attentionItems.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 animate-fade-in">
          {attentionItems.map((item) => (
            <div
              key={item.id}
              className="p-3.5 rounded-2xl bg-amber-50/90 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 text-xs flex items-start gap-2.5 shadow-xs"
            >
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-bold text-amber-900 dark:text-amber-200">{item.title}</div>
                <p className="text-amber-800/80 dark:text-amber-300/80 mt-0.5 leading-snug">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Middle 3-Column Analytics Row (Reference Inspired) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Patient Acuity & Capacity Curve (AreaChart) */}
        <Card className="lg:col-span-1 animate-slide-up stagger-2">
          <CardHeader className="mb-2">
            <CardTitle className="text-sm font-bold text-text-primary flex items-center gap-2">
              <Activity className="w-4 h-4 text-sky-400" />
              Patient Acuity Overview
            </CardTitle>
            <p className="text-[11px] text-text-muted">
              Waiting queue distribution across triage levels
            </p>
          </CardHeader>

          <CardContent>
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={[1, 2, 3, 4, 5].map((lvl) => ({
                    level: `L${lvl}`,
                    Waiting: acuityCounts[lvl] || 0,
                  }))}
                  margin={{ top: 10, right: 8, left: -24, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="acuityGlow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1d4ed8" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="#1d4ed8" stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-light)" />
                  <XAxis dataKey="level" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-surface-elevated)',
                      borderColor: 'var(--border-light)',
                      borderRadius: '12px',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="Waiting"
                    stroke="#1d4ed8"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#acuityGlow)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Ward Capacity Status (Glowing Bars) */}
        <Card className="lg:col-span-1 animate-slide-up stagger-3">
          <CardHeader className="mb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold text-text-primary flex items-center gap-2">
                <BedDouble className="w-4 h-4 text-purple-400" />
                Ward Capacity Status
              </CardTitle>
              <Link
                to="/beds"
                className="text-[11px] font-semibold text-sky-400 hover:text-sky-300 flex items-center gap-1"
              >
                View Details <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </CardHeader>

          <CardContent>
            <div className="space-y-4">
              {wardStats.map((ward) => {
                const barGradient =
                  ward.type === 'ICU'
                    ? 'linear-gradient(90deg, #1d4ed8 0%, #3b82f6 100%)'
                    : ward.type === 'STEP_DOWN'
                      ? 'linear-gradient(90deg, #b45309 0%, #d97706 100%)'
                      : 'linear-gradient(90deg, #15803d 0%, #16a34a 100%)';
                return (
                  <div key={ward.type} className="space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-text-primary">
                        {ward.type === 'STEP_DOWN'
                          ? 'Step-Down'
                          : ward.type === 'WARD'
                            ? 'General Ward'
                            : 'ICU'}
                      </span>
                      <span className="font-mono font-bold text-text-primary">
                        {formatPct(ward.rate)}
                      </span>
                    </div>
                    <div className="w-full h-2.5 rounded-full bg-border-light overflow-hidden">
                      <div
                        className="h-full rounded-full progress-shine transition-all duration-700"
                        style={{
                          width: `${Math.min(ward.rate * 100, 100)}%`,
                          background: barGradient,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity Feed (Live from /audit) */}
        <Card className="lg:col-span-1 animate-slide-up stagger-4">
          <CardHeader className="mb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold text-text-primary flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                Recent Activity
              </CardTitle>
              <Link
                to="/audit"
                className="text-[11px] font-semibold text-sky-400 hover:text-sky-300 flex items-center gap-1"
              >
                View All <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </CardHeader>

          <CardContent>
            {auditEntries.length === 0 ? (
              <div className="text-center py-8 text-xs text-text-muted">
                No recent allocation or lifecycle events recorded.
              </div>
            ) : (
              <div className="space-y-2.5">
                {auditEntries.slice(0, 4).map((entry, idx) => (
                  <div
                    key={`${entry.patient_id}-${entry.timestamp}-${idx}`}
                    className="flex items-center justify-between gap-2 p-2 rounded-xl bg-bg-surface-hover/50 border border-border-light/60 text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="w-7 h-7 rounded-full bg-sky-500/15 text-sky-400 flex items-center justify-center flex-shrink-0">
                        <CheckCircle className="w-3.5 h-3.5" />
                      </span>
                      <div className="min-w-0">
                        <div className="font-semibold text-text-primary truncate">
                          {entry.action}
                        </div>
                        <div className="text-[10px] text-text-muted truncate font-mono">
                          {entry.patient_id} {entry.bed_id ? `→ ${entry.bed_id}` : ''}
                        </div>
                      </div>
                    </div>
                    <span className="text-[10px] text-text-muted whitespace-nowrap">
                      {formatServerTimestamp(entry.timestamp).replace(' UTC', '')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* Bottom Row: Urgent Waiting Patients + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Quick Actions 2x2 Grid (Reference Inspired) */}
        <Card className="lg:col-span-1 animate-slide-up stagger-5">
          <CardHeader className="mb-3">
            <CardTitle className="text-sm font-bold text-text-primary flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <Link
                to="/queue"
                className="p-3.5 rounded-2xl border border-sky-500/30 bg-sky-500/10 hover:bg-sky-500/20 transition-all flex flex-col items-center justify-center text-center gap-2 card-interactive"
              >
                <Users className="w-5 h-5 text-sky-400" />
                <span className="text-xs font-semibold text-text-primary">Admission Queue</span>
              </Link>
              <Link
                to="/beds"
                className="p-3.5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 transition-all flex flex-col items-center justify-center text-center gap-2 card-interactive"
              >
                <BedDouble className="w-5 h-5 text-emerald-400" />
                <span className="text-xs font-semibold text-text-primary">Manage Beds</span>
              </Link>
              <Link
                to="/reports"
                className="p-3.5 rounded-2xl border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 transition-all flex flex-col items-center justify-center text-center gap-2 card-interactive"
              >
                <BarChart3 className="w-5 h-5 text-purple-400" />
                <span className="text-xs font-semibold text-text-primary">View Reports</span>
              </Link>
              <Link
                to="/surge"
                className="p-3.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 transition-all flex flex-col items-center justify-center text-center gap-2 card-interactive"
              >
                <ScrollText className="w-5 h-5 text-amber-400" />
                <span className="text-xs font-semibold text-text-primary">Surge Planner</span>
              </Link>
            </div>
            <div className="mt-4 pt-3 border-t border-border-light space-y-1.5">
              <div className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                Queue Acuity Breakdown
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[5, 4, 3, 2, 1].map((acuity) => (
                  <span
                    key={acuity}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-bg-surface-hover border border-border-light text-[10px] font-mono"
                    title={ACUITY_LABELS[acuity as AcuityLevel].label}
                  >
                    <AcuityBadge acuity={acuity} />
                    <span className="font-bold text-text-primary">{acuityCounts[acuity] || 0}</span>
                  </span>
                ))}
              </div>
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

      {/* Beds Awaiting Cleaning Queue */}
      {cleaningBeds.length > 0 && (
        <Card className="border-amber-500/30 bg-amber-500/5 animate-slide-in-up">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                Beds Awaiting Cleaning Turnover
              </CardTitle>
              <span className="text-xs font-mono font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-800 dark:text-amber-300">
                {cleaningBeds.length} pending
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {cleaningBeds.map((bed) => (
                <div
                  key={bed.bed_id}
                  className="p-3 rounded-xl bg-bg-surface border border-amber-500/30 flex items-center justify-between gap-3 card-interactive"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-text-primary">
                        {bed.bed_id}
                      </span>
                      <WardBadge bedType={bed.bed_type} />
                    </div>
                    <span className="text-[11px] text-text-muted block mt-0.5">
                      {bed.ward}
                    </span>
                  </div>
                  {canCompleteCleaning && (
                    <Button
                      size="sm"
                      variant="primary"
                      isLoading={
                        cleanBedMutation.isPending &&
                        cleanBedMutation.variables === bed.bed_id
                      }
                      onClick={() => handleCompleteCleaning(bed.bed_id)}
                    >
                      Mark Clean
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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
