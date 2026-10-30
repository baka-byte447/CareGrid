import React, { useState } from 'react';
import { useMetrics, useBeds, usePatients } from '@/api/hooks';
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
  const {
    data: metrics,
    isLoading: metricsLoading,
    error: metricsError,
    refetch: refetchMetrics,
    dataUpdatedAt,
  } = useMetrics();

  const {
    data: bedsData,
    isLoading: bedsLoading,
    error: bedsError,
    refetch: refetchBeds,
  } = useBeds();

  const {
    data: patientsData,
    isLoading: patientsLoading,
    error: patientsError,
    refetch: refetchPatients,
  } = usePatients();

  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);

  const isLoading = metricsLoading || bedsLoading || patientsLoading;
  const isError = metricsError || bedsError || patientsError;

  const handleRetryAll = () => {
    refetchMetrics();
    refetchBeds();
    refetchPatients();
  };

  if (isLoading && !metrics) {
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

  if (isError && !metrics) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Hospital Command Centre"
          description="Real-time capacity tracking, triage acuity distribution, and operational alerts."
        />
        <ErrorState
          error={metricsError || bedsError || patientsError}
          onRetry={handleRetryAll}
        />
      </div>
    );
  }

  const beds: Bed[] = bedsData || [];
  const patients: Patient[] = patientsData || [];

  // Group beds by ward type
  const wardStats = WARD_TYPE_LIST.map((type) => {
    const wardBeds = beds.filter((b: Bed) => b.bed_type === type);
    const total = wardBeds.length;
    const occupied = wardBeds.filter((b: Bed) => b.status === 'OCCUPIED').length;
    const available = wardBeds.filter((b: Bed) => b.status === 'AVAILABLE').length;
    const rate = total > 0 ? occupied / total : 0;
    return { type, total, occupied, available, rate };
  });

  // Calculate waiting queue breakdown by acuity
  const waitingPatients = patients.filter((p: Patient) => p.current_status === 'WAITING');
  const criticalWaiting = waitingPatients.filter((p: Patient) => p.acuity >= 4);

  const acuityCounts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  waitingPatients.forEach((p) => {
    if (acuityCounts[p.acuity] !== undefined) {
      acuityCounts[p.acuity]++;
    }
  });

  // Needs Attention items
  const attentionItems: { id: string; title: string; desc: string; severity: 'high' | 'medium' }[] = [];

  if (metrics && metrics.ventilators_available <= 1) {
    attentionItems.push({
      id: 'vent-shortage',
      title: 'Ventilator Inventory Critical',
      desc: `Only ${metrics.ventilators_available} ventilator(s) available across hospital.`,
      severity: 'high',
    });
  }

  const icuStat = wardStats.find((w) => w.type === 'ICU');
  if (icuStat && icuStat.available <= 1 && icuStat.total > 0) {
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
      <PageHeader
        title="Hospital Command Centre"
        description="Real-time capacity tracking, triage acuity distribution, and operational alerts."
        actions={
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-text-muted">
              Auto-refresh 30s &bull; Last sync: {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '—'}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetryAll}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
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
          value={metrics ? formatPct(metrics.bed_occupancy_rate) : '—'}
          subtext={metrics ? `${metrics.beds_occupied} of ${metrics.beds_total} beds occupied` : undefined}
          icon={<BedDouble className="w-5 h-5" />}
          accent={metrics && metrics.bed_occupancy_rate > 0.85 ? 'red' : 'primary'}
        />

        <MetricCard
          label="Admission Queue"
          value={metrics?.patients_waiting ?? 0}
          subtext={`${criticalWaiting.length} high-acuity (L4/L5) pending`}
          icon={<Users className="w-5 h-5" />}
          accent={criticalWaiting.length > 0 ? 'amber' : 'purple'}
        />

        <MetricCard
          label="Ventilator Fleet"
          value={metrics ? `${metrics.ventilators_available} / ${metrics.ventilators_total}` : '—'}
          subtext={metrics ? `${metrics.ventilators_in_use} in clinical use` : undefined}
          icon={<Wind className="w-5 h-5" />}
          accent={metrics && metrics.ventilators_available <= 1 ? 'red' : 'green'}
        />

        <MetricCard
          label="Allocations Made"
          value={metrics?.approved_allocations ?? 0}
          subtext={`${metrics?.patients_admitted ?? 0} total patients admitted`}
          icon={<CheckCircle className="w-5 h-5" />}
          accent="green"
        />
      </div>

      {/* Main Grid: Needs Attention + Ward Capacity */}
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
                {attentionItems.length} {attentionItems.length === 1 ? 'Alert' : 'Alerts'}
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
                    <p className="text-text-secondary">{item.desc}</p>
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
                <div key={ward.type} className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-text-primary">
                      {ward.type === 'STEP_DOWN' ? 'Step-Down Unit' : ward.type === 'WARD' ? 'General Ward' : 'Intensive Care Unit (ICU)'}
                    </span>
                    <span className="font-mono text-text-secondary">
                      {ward.available} free / {ward.total} total ({formatPct(ward.rate)})
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
                      style={{ width: `${Math.min(ward.rate * 100, 100)}%` }}
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
                const pct = waitingPatients.length > 0 ? (count / waitingPatients.length) * 100 : 0;
                return (
                  <div key={acuity} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <AcuityBadge acuity={acuity} />
                      <span className="text-text-secondary font-medium">
                        {ACUITY_LABELS[acuity as AcuityLevel].label}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-text-primary">{count}</span>
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
                      <th className="pb-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-light/60">
                    {criticalWaiting.slice(0, 5).map((p) => (
                      <tr key={p.patient_id} className="hover:bg-bg-surface-hover/60">
                        <td className="py-2.5 font-mono font-semibold text-brand-primary">
                          {p.patient_id}
                        </td>
                        <td className="py-2.5">
                          <AcuityBadge acuity={p.acuity} showLabel />
                        </td>
                        <td className="py-2.5 font-medium">{p.specialty}</td>
                        <td className="py-2.5">
                          <RequirementChips
                            isolationRequired={p.isolation_required}
                            ventilatorRequired={p.ventilator_required}
                          />
                        </td>
                        <td className="py-2.5 text-right">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => setSelectedPatient(p)}
                            rightIcon={<ArrowRight className="w-3 h-3" />}
                          >
                            Allocate
                          </Button>
                        </td>
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
