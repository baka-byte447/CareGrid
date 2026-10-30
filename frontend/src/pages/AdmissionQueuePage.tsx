import React, { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usePatients } from '@/api/hooks';
import { Patient } from '@/api/schemas';
import { PageHeader } from '@/components/layout/PageHeader';
import { PatientRow } from '@/components/domain/PatientRow';
import { TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Input, Select } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { RecommendationDrawer } from './RecommendationDrawer';
import { Search, Filter, RefreshCw, Users, ShieldAlert, Wind } from 'lucide-react';

export const AdmissionQueuePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data, isLoading, error, refetch } = usePatients();

  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);

  // Filters read from URL query params for bookmarking & state persistence
  const statusFilter = searchParams.get('status') || 'WAITING';
  const acuityFilter = searchParams.get('acuity') || 'ALL';
  const specialtyFilter = searchParams.get('specialty') || 'ALL';
  const searchQuery = searchParams.get('q') || '';
  const isolationFilter = searchParams.get('isolation') === 'true';
  const ventilatorFilter = searchParams.get('ventilator') === 'true';
  const sortBy = searchParams.get('sort') || 'acuity_desc';

  // Pagination state
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const updateParam = (key: string, value: string | null) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === null || value === '' || value === 'ALL') {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      return next;
    });
    setPage(1);
  };

  const patients: Patient[] = useMemo(() => data || [], [data]);

  // Extract unique specialties for filter dropdown
  const specialties = useMemo(() => {
    const set = new Set<string>();
    patients.forEach((p) => {
      if (p.specialty) set.add(p.specialty);
    });
    return Array.from(set).sort();
  }, [patients]);

  // Apply filters
  const filteredPatients = useMemo(() => {
    return patients.filter((p) => {
      if (statusFilter !== 'ALL' && p.current_status !== statusFilter) return false;
      if (acuityFilter !== 'ALL' && p.acuity !== parseInt(acuityFilter, 10)) return false;
      if (specialtyFilter !== 'ALL' && p.specialty !== specialtyFilter) return false;
      if (isolationFilter && !p.isolation_required) return false;
      if (ventilatorFilter && !p.ventilator_required) return false;
      if (searchQuery && !p.patient_id.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [patients, statusFilter, acuityFilter, specialtyFilter, isolationFilter, ventilatorFilter, searchQuery]);

  // Apply sorting
  const sortedPatients = useMemo(() => {
    return [...filteredPatients].sort((a, b) => {
      if (sortBy === 'acuity_desc') return b.acuity - a.acuity;
      if (sortBy === 'acuity_asc') return a.acuity - b.acuity;
      if (sortBy === 'los_desc') return b.predicted_los - a.predicted_los;
      if (sortBy === 'los_asc') return a.predicted_los - b.predicted_los;
      if (sortBy === 'arrival_desc') return b.arrival_time.localeCompare(a.arrival_time);
      if (sortBy === 'arrival_asc') return a.arrival_time.localeCompare(b.arrival_time);
      return 0;
    });
  }, [filteredPatients, sortBy]);

  // Paginated slice
  const totalPages = Math.ceil(sortedPatients.length / pageSize) || 1;
  const paginatedPatients = sortedPatients.slice((page - 1) * pageSize, page * pageSize);

  const waitingCount = patients.filter((p) => p.current_status === 'WAITING').length;
  const admittedCount = patients.filter((p) => p.current_status === 'ADMITTED').length;

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Patient Admission Queue"
          description="Triage-prioritized admission queue with reinforcement learning bed allocation."
        />
        <TableSkeleton rows={8} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Patient Admission Queue"
          description="Triage-prioritized admission queue with reinforcement learning bed allocation."
        />
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Patient Admission Queue"
        description="Triage-prioritized admission queue with reinforcement learning bed allocation."
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

      {/* Filter and Search Bar */}
      <div className="bg-bg-surface border border-border-light rounded-xl p-4 shadow-card space-y-3">
        <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
          {/* Search box */}
          <div className="w-full md:w-72">
            <Input
              placeholder="Search by Patient ID (e.g. PAT-)..."
              value={searchQuery}
              onChange={(e) => updateParam('q', e.target.value)}
              leftIcon={<Search className="w-4 h-4 text-text-muted" />}
            />
          </div>

          {/* Quick status tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-bg-page rounded-lg border border-border-light w-full md:w-auto">
            <button
              onClick={() => updateParam('status', 'WAITING')}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                statusFilter === 'WAITING'
                  ? 'bg-bg-surface text-brand-primary shadow-sm'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              Waiting ({waitingCount})
            </button>
            <button
              onClick={() => updateParam('status', 'ADMITTED')}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                statusFilter === 'ADMITTED'
                  ? 'bg-bg-surface text-brand-primary shadow-sm'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              Admitted ({admittedCount})
            </button>
            <button
              onClick={() => updateParam('status', 'ALL')}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                statusFilter === 'ALL'
                  ? 'bg-bg-surface text-brand-primary shadow-sm'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              All ({patients.length})
            </button>
          </div>
        </div>

        {/* Detailed filters */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border-light/60 text-xs">
          <div className="flex items-center gap-1.5 text-text-muted">
            <Filter className="w-3.5 h-3.5" />
            <span className="font-semibold">Filter:</span>
          </div>

          <Select
            value={acuityFilter}
            onChange={(e) => updateParam('acuity', e.target.value)}
            className="text-xs py-1 px-2.5 h-8"
          >
            <option value="ALL">All Acuity Levels</option>
            <option value="5">Acuity 5 (Resuscitation)</option>
            <option value="4">Acuity 4 (Emergent)</option>
            <option value="3">Acuity 3 (Urgent)</option>
            <option value="2">Acuity 2 (Less Urgent)</option>
            <option value="1">Acuity 1 (Non-Urgent)</option>
          </Select>

          <Select
            value={specialtyFilter}
            onChange={(e) => updateParam('specialty', e.target.value)}
            className="text-xs py-1 px-2.5 h-8"
          >
            <option value="ALL">All Specialties</option>
            {specialties.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>

          <Select
            value={sortBy}
            onChange={(e) => updateParam('sort', e.target.value)}
            className="text-xs py-1 px-2.5 h-8"
          >
            <option value="acuity_desc">Sort: Acuity (Highest First)</option>
            <option value="acuity_asc">Sort: Acuity (Lowest First)</option>
            <option value="arrival_desc">Sort: Arrival (Latest First)</option>
            <option value="arrival_asc">Sort: Arrival (Earliest First)</option>
            <option value="los_desc">Sort: Predicted LOS (Longest)</option>
            <option value="los_asc">Sort: Predicted LOS (Shortest)</option>
          </Select>

          <button
            onClick={() => updateParam('isolation', isolationFilter ? null : 'true')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded border text-xs font-medium transition-colors ${
              isolationFilter
                ? 'bg-pink-500/15 border-pink-500/40 text-pink-700 dark:text-pink-300'
                : 'border-border-medium text-text-secondary hover:bg-bg-surface-hover'
            }`}
          >
            <ShieldAlert className="w-3 h-3" />
            Isolation Only
          </button>

          <button
            onClick={() => updateParam('ventilator', ventilatorFilter ? null : 'true')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded border text-xs font-medium transition-colors ${
              ventilatorFilter
                ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-700 dark:text-indigo-300'
                : 'border-border-medium text-text-secondary hover:bg-bg-surface-hover'
            }`}
          >
            <Wind className="w-3 h-3" />
            Ventilator Only
          </button>

          {(statusFilter !== 'WAITING' ||
            acuityFilter !== 'ALL' ||
            specialtyFilter !== 'ALL' ||
            isolationFilter ||
            ventilatorFilter ||
            searchQuery) && (
            <button
              onClick={() => setSearchParams(new URLSearchParams())}
              className="text-brand-primary hover:underline text-xs ml-auto font-medium"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Patient Table */}
      <div className="bg-bg-surface border border-border-light rounded-xl shadow-card overflow-hidden">
        {sortedPatients.length === 0 ? (
          <EmptyState
            title="No matching patients found"
            description="Try modifying search keywords or removing active triage filters."
            icon={<Users className="w-8 h-8 text-text-muted" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-bg-page/75 border-b border-border-light text-text-muted uppercase text-[11px] font-semibold tracking-wider">
                  <th className="p-3.5">Patient ID</th>
                  <th className="p-3.5">Age Group</th>
                  <th className="p-3.5">Acuity</th>
                  <th className="p-3.5">Specialty</th>
                  <th className="p-3.5">Predicted LOS</th>
                  <th className="p-3.5">Requirements</th>
                  <th className="p-3.5">Arrival (Simulated)</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedPatients.map((patient) => (
                  <PatientRow
                    key={patient.patient_id}
                    patient={patient}
                    isSelected={selectedPatient?.patient_id === patient.patient_id}
                    onSelect={(p) => setSelectedPatient(p)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {sortedPatients.length > pageSize && (
          <div className="p-4 border-t border-border-light flex items-center justify-between text-xs text-text-muted">
            <span>
              Showing {(page - 1) * pageSize + 1} to{' '}
              {Math.min(page * pageSize, sortedPatients.length)} of {sortedPatients.length} patients
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1}
              >
                Previous
              </Button>
              <span className="font-mono text-text-primary">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page >= totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Allocation Drawer / Modal */}
      {selectedPatient && (
        <RecommendationDrawer
          patient={selectedPatient}
          isOpen={!!selectedPatient}
          onClose={() => setSelectedPatient(null)}
          onSuccess={() => {
            setSelectedPatient(null);
            refetch();
          }}
        />
      )}
    </div>
  );
};
