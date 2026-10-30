import React, { useState, useMemo } from 'react';
import { useBeds } from '@/api/hooks';
import { Bed } from '@/api/schemas';
import { PageHeader } from '@/components/layout/PageHeader';
import { BedTile } from '@/components/domain/BedTile';
import { WardBadge } from '@/components/domain/WardBadge';
import { StatusDot } from '@/components/domain/StatusDot';
import { BedGridSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { Dialog } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Input';
import { formatPct } from '@/lib/format';
import { BedDouble, Shield, RefreshCw } from 'lucide-react';

export const BedManagementPage: React.FC = () => {
  const { data, isLoading, error, refetch } = useBeds();

  const [wardFilter, setWardFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isolationFilter, setIsolationFilter] = useState(false);
  const [inspectedBed, setInspectedBed] = useState<Bed | null>(null);

  const beds: Bed[] = useMemo(() => data || [], [data]);

  // Extract unique ward names
  const wards = useMemo(() => {
    const set = new Set<string>();
    beds.forEach((b) => set.add(b.ward));
    return Array.from(set).sort();
  }, [beds]);

  // Filter beds
  const filteredBeds = useMemo(() => {
    return beds.filter((b) => {
      if (wardFilter !== 'ALL' && b.ward !== wardFilter) return false;
      if (statusFilter !== 'ALL' && b.status !== statusFilter) return false;
      if (isolationFilter && !b.isolation_capable) return false;
      return true;
    });
  }, [beds, wardFilter, statusFilter, isolationFilter]);

  // Group filtered beds by ward
  const bedsByWard = useMemo(() => {
    const groups: Record<string, Bed[]> = {};
    filteredBeds.forEach((bed) => {
      if (!groups[bed.ward]) {
        groups[bed.ward] = [];
      }
      groups[bed.ward].push(bed);
    });
    return groups;
  }, [filteredBeds]);

  // Stats calculation
  const totalBeds = beds.length;
  const availableBeds = beds.filter((b) => b.status === 'AVAILABLE').length;
  const occupiedBeds = beds.filter((b) => b.status === 'OCCUPIED').length;
  const overallOccupancy = totalBeds > 0 ? occupiedBeds / totalBeds : 0;

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Hospital Bed Management"
          description="Real-time bed availability across clinical wards and isolation facilities."
        />
        <BedGridSkeleton />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Hospital Bed Management"
          description="Real-time bed availability across clinical wards and isolation facilities."
        />
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospital Bed Management"
        description="Real-time bed availability across clinical wards and isolation facilities."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        }
      />

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface">
          <span className="text-xs text-text-muted uppercase font-semibold">Total Fleet</span>
          <div className="text-2xl font-bold font-mono text-text-primary mt-1">{totalBeds}</div>
          <span className="text-[11px] text-text-muted">Registered hospital beds</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface">
          <span className="text-xs text-text-muted uppercase font-semibold">Available</span>
          <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {availableBeds}
          </div>
          <span className="text-[11px] text-text-muted">Ready for allocation</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface">
          <span className="text-xs text-text-muted uppercase font-semibold">Occupied</span>
          <div className="text-2xl font-bold font-mono text-red-600 dark:text-red-400 mt-1">
            {occupiedBeds}
          </div>
          <span className="text-[11px] text-text-muted">Currently in use</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface">
          <span className="text-xs text-text-muted uppercase font-semibold">Occupancy Rate</span>
          <div className="text-2xl font-bold font-mono text-brand-primary mt-1">
            {formatPct(overallOccupancy)}
          </div>
          <span className="text-[11px] text-text-muted">Global bed utilization</span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-bg-surface border border-border-light rounded-xl shadow-card text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={wardFilter}
            onChange={(e) => setWardFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Wards ({wards.length})</option>
            {wards.map((w) => (
              <option key={w} value={w}>
                Ward: {w}
              </option>
            ))}
          </Select>

          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Statuses</option>
            <option value="AVAILABLE">Available Only</option>
            <option value="OCCUPIED">Occupied Only</option>
          </Select>

          <button
            onClick={() => setIsolationFilter((prev) => !prev)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border font-medium transition-colors ${
              isolationFilter
                ? 'bg-purple-500/15 border-purple-500/40 text-purple-700 dark:text-purple-300'
                : 'border-border-medium text-text-secondary hover:bg-bg-surface-hover'
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            Isolation Capable Only
          </button>
        </div>

        <div className="text-text-muted text-xs">
          Showing <strong>{filteredBeds.length}</strong> of {totalBeds} beds
        </div>
      </div>

      {/* Grouped Wards and Bed Tiles */}
      <div className="space-y-6">
        {Object.entries(bedsByWard).map(([wardName, wardBeds]) => {
          const wardTotal = wardBeds.length;
          const wardAvailable = wardBeds.filter((b) => b.status === 'AVAILABLE').length;
          const wardBedType = wardBeds[0]?.bed_type || 'WARD';

          return (
            <div
              key={wardName}
              className="p-5 rounded-xl border border-border-light bg-bg-surface shadow-card space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-light pb-3">
                <div className="flex items-center gap-3">
                  <h3 className="text-base font-bold text-text-primary tracking-tight">
                    {wardName}
                  </h3>
                  <WardBadge bedType={wardBedType} />
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-text-secondary">
                    <strong className="text-emerald-600 dark:text-emerald-400 font-mono">
                      {wardAvailable}
                    </strong>{' '}
                    available of <strong className="font-mono">{wardTotal}</strong> beds
                  </span>
                  <div className="w-24 h-2 rounded-full bg-border-light overflow-hidden">
                    <div
                      className="h-full bg-brand-primary"
                      style={{
                        width: `${wardTotal > 0 ? ((wardTotal - wardAvailable) / wardTotal) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Grid of Beds */}
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
                {wardBeds.map((bed) => (
                  <BedTile
                    key={bed.bed_id}
                    bed={bed}
                    onClick={(b) => setInspectedBed(b)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Bed Inspection Dialog */}
      {inspectedBed && (
        <Dialog
          isOpen={!!inspectedBed}
          onClose={() => setInspectedBed(null)}
          title={`Bed Details — ${inspectedBed.bed_id}`}
          description={`Clinical Ward: ${inspectedBed.ward}`}
          maxWidth="sm"
          footer={
            <Button variant="secondary" size="sm" onClick={() => setInspectedBed(null)}>
              Close
            </Button>
          }
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-bg-surface-hover border border-border-light space-y-2.5">
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Bed ID</span>
                <span className="font-mono font-bold text-sm text-text-primary">
                  {inspectedBed.bed_id}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Ward Location</span>
                <span className="font-semibold text-text-primary">{inspectedBed.ward}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Care Tier</span>
                <WardBadge bedType={inspectedBed.bed_type} />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Availability</span>
                <span className="inline-flex items-center gap-1.5 font-semibold">
                  <StatusDot status={inspectedBed.status} />
                  <span className={inspectedBed.status === 'AVAILABLE' ? 'text-emerald-600' : 'text-red-600'}>
                    {inspectedBed.status}
                  </span>
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Isolation Capable</span>
                <span className="font-medium">
                  {inspectedBed.isolation_capable ? 'Yes (Negative Pressure)' : 'Standard Bed'}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-bg-page border border-border-light text-text-muted text-[11px] leading-relaxed">
              <BedDouble className="w-3.5 h-3.5 inline mr-1 text-brand-primary" />
              <strong>System Notice:</strong> Patient occupancy and admission history are logged through the Audit Log and Admission Queue.
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
};
