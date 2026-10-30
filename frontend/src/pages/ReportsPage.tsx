import React, { useMemo } from 'react';
import { useMetrics, useBeds, usePatients } from '@/api/hooks';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { PageSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { Bed, Patient } from '@/api/schemas';
import { formatPct } from '@/lib/format';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Info, BarChart3, AlertCircle } from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const { data: metrics, isLoading: mLoading, error: mError } = useMetrics();
  const { data: bedsData, isLoading: bLoading, error: bError } = useBeds();
  const { data: patientsData, isLoading: pLoading, error: pError } = usePatients();

  const isLoading = mLoading || bLoading || pLoading;
  const isError = mError || bError || pError;

  const beds: Bed[] = useMemo(() => bedsData || [], [bedsData]);
  const patients: Patient[] = useMemo(() => patientsData || [], [patientsData]);

  // 1. Acuity Distribution data
  const acuityData = useMemo(() => {
    const counts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    patients.forEach((p) => {
      if (counts[p.acuity] !== undefined) counts[p.acuity]++;
    });
    return [
      { name: 'L1 Non-Urgent', count: counts[1], fill: '#22c55e' },
      { name: 'L2 Less Urgent', count: counts[2], fill: '#84cc16' },
      { name: 'L3 Urgent', count: counts[3], fill: '#f59e0b' },
      { name: 'L4 Emergent', count: counts[4], fill: '#f97316' },
      { name: 'L5 Resus', count: counts[5], fill: '#dc2626' },
    ];
  }, [patients]);

  // 2. Specialty Distribution data
  const specialtyData = useMemo(() => {
    const counts: Record<string, number> = {};
    patients.forEach((p) => {
      counts[p.specialty] = (counts[p.specialty] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [patients]);

  // 3. Ward Utilization data
  const wardData = useMemo(() => {
    const map: Record<string, { total: number; occupied: number }> = {};
    beds.forEach((b) => {
      if (!map[b.ward]) map[b.ward] = { total: 0, occupied: 0 };
      map[b.ward].total++;
      if (b.status === 'OCCUPIED') map[b.ward].occupied++;
    });
    return Object.entries(map).map(([ward, stat]) => ({
      ward,
      occupancy: stat.total > 0 ? (stat.occupied / stat.total) * 100 : 0,
      total: stat.total,
      occupied: stat.occupied,
    }));
  }, [beds]);

  // 4. Age Group Distribution
  const ageGroupData = useMemo(() => {
    const counts: Record<string, number> = {};
    patients.forEach((p) => {
      counts[p.age_group] = (counts[p.age_group] || 0) + 1;
    });
    return Object.entries(counts).map(([group, count]) => ({ group, count }));
  }, [patients]);

  if (isLoading && !metrics) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Analytical Reports"
          description="Operational distributions aggregated directly from current active hospital records."
        />
        <PageSkeleton />
      </div>
    );
  }

  if (isError && !metrics) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Analytical Reports"
          description="Operational distributions aggregated directly from current active hospital records."
        />
        <ErrorState error={mError || bError || pError} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Clinical Analytical Reports"
        description="Operational distributions aggregated directly from current active hospital records."
        badge={
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-700 dark:text-sky-400 border border-sky-500/20">
            <BarChart3 className="w-3 h-3 text-sky-500" />
            Live Distribution Analysis
          </span>
        }
      />

      {/* Backend API Limitations Notice (Strictly enforced: No invented time series or fake comparisons) */}
      <div className="p-4 bg-bg-surface border border-border-light rounded-xl space-y-2 text-xs">
        <div className="flex items-center gap-2 text-text-primary font-semibold">
          <Info className="w-4 h-4 text-brand-primary flex-shrink-0" />
          <span>Analytical Scope & Data Provenance Notice</span>
        </div>
        <p className="text-text-muted leading-relaxed">
          The charts below depict empirical cross-sectional distributions computed from active backend records (`/patients`, `/beds`, `/metrics`).
        </p>
        <div className="flex flex-col sm:flex-row gap-3 pt-1 text-[11px] text-text-muted">
          <div className="flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
            <span><strong>Time-Series:</strong> Historical trend lines require a backend time-series endpoint.</span>
          </div>
          <div className="flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
            <span><strong>Policy Comparison:</strong> RL vs heuristic baseline comparisons require simulation benchmark endpoints.</span>
          </div>
        </div>
      </div>

      {/* Grid of Real Distribution Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Acuity Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase font-bold text-text-secondary">
              Triage Acuity Distribution (Patient Population)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={acuityData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" />
                  <YAxis tick={{ fontSize: 11 }} />
                  <RechartsTooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {acuityData.map((entry: { name: string; count: number; fill: string }, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-between text-[11px] text-text-muted pt-2 border-t border-border-light mt-2">
              <span>Total patients: {patients.length}</span>
              <span>Resuscitation (L5): {acuityData[4]?.count || 0}</span>
            </div>
          </CardContent>
        </Card>

        {/* Specialty Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase font-bold text-text-secondary">
              Patient Volume by Clinical Specialty
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={specialtyData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" />
                  <YAxis tick={{ fontSize: 11 }} />
                  <RechartsTooltip />
                  <Bar dataKey="count" fill="#1d6fa4" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-between text-[11px] text-text-muted pt-2 border-t border-border-light mt-2">
              <span>Distinct specialties: {specialtyData.length}</span>
              <span>Leading volume: {specialtyData[0]?.name || '—'}</span>
            </div>
          </CardContent>
        </Card>

        {/* Ward Occupancy % */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase font-bold text-text-secondary">
              Ward Bed Occupancy Rate (%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={wardData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="ward" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
                  <RechartsTooltip formatter={(val: any) => [`${Number(val).toFixed(1)}%`, 'Occupancy']} />
                  <Bar dataKey="occupancy" fill="#0284c7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-between text-[11px] text-text-muted pt-2 border-t border-border-light mt-2">
              <span>Hospital wards: {wardData.length}</span>
              <span>Global occupancy: {metrics ? formatPct(metrics.bed_occupancy_rate) : '—'}</span>
            </div>
          </CardContent>
        </Card>

        {/* Age Group Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase font-bold text-text-secondary">
              Patient Age Group Demographics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ageGroupData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="group" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <RechartsTooltip />
                  <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-between text-[11px] text-text-muted pt-2 border-t border-border-light mt-2">
              <span>Patient demographics</span>
              <span>Categories: {ageGroupData.length}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
