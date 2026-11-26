import React, { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  usePatients,
  useBeds,
  useIntakePatient,
  useDischargePatient,
  useTransferPatient,
  getErrorMessage,
} from '@/api/hooks';
import { useAuth } from '@/auth/AuthContext';
import { Patient } from '@/api/schemas';
import { PageHeader } from '@/components/layout/PageHeader';
import { PatientRow } from '@/components/domain/PatientRow';
import { TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { useToast } from '@/components/feedback/Toast';
import { Input, Select } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { RecommendationDrawer } from './RecommendationDrawer';
import {
  Search,
  Filter,
  RefreshCw,
  Users,
  ShieldAlert,
  Wind,
  UserPlus,
  ArrowLeftRight,
} from 'lucide-react';

export const AdmissionQueuePage: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data, isLoading, error, refetch } = usePatients();
  const { data: bedsData } = useBeds();

  const intakeMutation = useIntakePatient();
  const dischargeMutation = useDischargePatient();
  const transferMutation = useTransferPatient();

  const canIntake =
    user?.role === 'admin' || user?.role === 'doctor' || user?.role === 'nurse';
  const canAllocate =
    user?.role === 'admin' || user?.role === 'doctor';
  const canManageAdmitted =
    user?.role === 'admin' || user?.role === 'doctor';

  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [isIntakeOpen, setIsIntakeOpen] = useState(false);
  const [transferPatient, setTransferPatient] = useState<Patient | null>(null);
  const [destinationBedId, setDestinationBedId] = useState('');

  // Intake form state
  const [ageGroup, setAgeGroup] = useState('31-50');
  const [acuity, setAcuity] = useState(3);
  const [specialty, setSpecialty] = useState('General Medicine');
  const [predictedLos, setPredictedLos] = useState('3.5');
  const [isolationRequired, setIsolationRequired] = useState(false);
  const [ventilatorRequired, setVentilatorRequired] = useState(false);

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
  const dischargedCount = patients.filter((p) => p.current_status === 'DISCHARGED').length;

  const availableBeds = useMemo(
    () => (bedsData || []).filter((b) => b.status === 'AVAILABLE'),
    [bedsData]
  );

  const handleIntakeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const los = parseFloat(predictedLos);
    if (Number.isNaN(los) || los <= 0) {
      showToast({
        type: 'error',
        title: 'Invalid LOS',
        message: 'Predicted length of stay must be a positive number.',
      });
      return;
    }

    intakeMutation.mutate(
      {
        age_group: ageGroup,
        acuity,
        specialty,
        predicted_los: los,
        isolation_required: isolationRequired,
        ventilator_required: ventilatorRequired,
      },
      {
        onSuccess: (res) => {
          showToast({
            type: 'success',
            title: 'Patient Admitted to Queue',
            message: `Patient ${res.patient_id} registered (Encounter #${res.encounter_id}).`,
          });
          setIsIntakeOpen(false);
          setIsolationRequired(false);
          setVentilatorRequired(false);
          updateParam('status', 'WAITING');
        },
        onError: (err) => {
          showToast({
            type: 'error',
            title: 'Intake Failed',
            message: getErrorMessage(err),
          });
        },
      }
    );
  };

  const handleDischarge = (patient: Patient) => {
    dischargeMutation.mutate(
      { patient_id: patient.patient_id, release_reason: 'clinical_discharge' },
      {
        onSuccess: (res) => {
          showToast({
            type: 'success',
            title: 'Patient Discharged',
            message: `${res.patient_id} discharged. Bed ${res.bed_id} moved to CLEANING.`,
          });
        },
        onError: (err) => {
          showToast({
            type: 'error',
            title: 'Discharge Failed',
            message: getErrorMessage(err),
          });
        },
      }
    );
  };

  const handleTransferSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!transferPatient || !destinationBedId) return;
    transferMutation.mutate(
      {
        patient_id: transferPatient.patient_id,
        destination_bed_id: destinationBedId,
        release_reason: 'ward_transfer',
      },
      {
        onSuccess: (res) => {
          showToast({
            type: 'success',
            title: 'Transfer Complete',
            message: `${res.patient_id} transferred from ${res.from_bed_id} to ${res.to_bed_id}.`,
          });
          setTransferPatient(null);
          setDestinationBedId('');
        },
        onError: (err) => {
          showToast({
            type: 'error',
            title: 'Transfer Failed',
            message: getErrorMessage(err),
          });
        },
      }
    );
  };

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
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Patient Admission Queue"
        description="Triage-prioritized admission queue with reinforcement learning bed allocation."
        actions={
          <div className="flex items-center gap-2">
            {canIntake && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsIntakeOpen(true)}
                leftIcon={<UserPlus className="w-3.5 h-3.5" />}
              >
                New Patient
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
          </div>
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
          <div className="flex items-center gap-1.5 p-1.5 bg-bg-page/80 backdrop-blur-md rounded-2xl border border-border-light w-full md:w-auto">
            <button
              onClick={() => updateParam('status', 'WAITING')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                statusFilter === 'WAITING'
                  ? 'bg-brand-primary text-white dark:text-slate-950 shadow-glow animate-tab-pop'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-surface-hover/60'
              }`}
            >
              Waiting ({waitingCount})
            </button>
            <button
              onClick={() => updateParam('status', 'ADMITTED')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                statusFilter === 'ADMITTED'
                  ? 'bg-brand-primary text-white dark:text-slate-950 shadow-glow animate-tab-pop'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-surface-hover/60'
              }`}
            >
              Admitted ({admittedCount})
            </button>
            <button
              onClick={() => updateParam('status', 'DISCHARGED')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                statusFilter === 'DISCHARGED'
                  ? 'bg-brand-primary text-white dark:text-slate-950 shadow-glow animate-tab-pop'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-surface-hover/60'
              }`}
            >
              Discharged ({dischargedCount})
            </button>
            <button
              onClick={() => updateParam('status', 'ALL')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                statusFilter === 'ALL'
                  ? 'bg-brand-primary text-white dark:text-slate-950 shadow-glow animate-tab-pop'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-surface-hover/60'
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
      <div
        key={statusFilter}
        className="glass-panel border border-border-light rounded-3xl overflow-hidden animate-page-enter"
      >
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
                    canAllocate={canAllocate}
                    canManageAdmitted={canManageAdmitted}
                    onSelect={(p) => setSelectedPatient(p)}
                    onDischarge={handleDischarge}
                    onTransfer={(p) => {
                      setTransferPatient(p);
                      setDestinationBedId(availableBeds[0]?.bed_id ?? '');
                    }}
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

      {/* New Patient Intake Modal */}
      <Dialog
        isOpen={isIntakeOpen}
        onClose={() => setIsIntakeOpen(false)}
        title="Register New Patient Intake"
        description="Creates a new patient record and opens an active clinical encounter."
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsIntakeOpen(false)}
              disabled={intakeMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              form="patient-intake-form"
              isLoading={intakeMutation.isPending}
              leftIcon={<UserPlus className="w-3.5 h-3.5" />}
            >
              Register Patient
            </Button>
          </div>
        }
      >
        <form id="patient-intake-form" onSubmit={handleIntakeSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-text-primary mb-1">
                Age Group
              </label>
              <Select
                value={ageGroup}
                onChange={(e) => setAgeGroup(e.target.value)}
                className="w-full h-9 text-xs"
              >
                <option value="0-17">0-17 (Pediatric)</option>
                <option value="18-30">18-30 (Young Adult)</option>
                <option value="31-50">31-50 (Adult)</option>
                <option value="51-70">51-70 (Older Adult)</option>
                <option value="71+">71+ (Geriatric)</option>
              </Select>
            </div>
            <div>
              <label className="block font-semibold text-text-primary mb-1">
                Predicted LOS (Days)
              </label>
              <Input
                type="number"
                step="0.5"
                min="0.5"
                max="60"
                value={predictedLos}
                onChange={(e) => setPredictedLos(e.target.value)}
                required
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-text-primary mb-1.5">
              Triage Acuity Level
            </label>
            <div className="grid grid-cols-5 gap-1.5">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setAcuity(level)}
                  className={`py-2 rounded-lg border text-xs font-bold transition-all ${
                    acuity === level
                      ? 'bg-brand-primary text-white border-brand-primary shadow-sm'
                      : 'bg-bg-surface border-border-medium text-text-secondary hover:bg-bg-surface-hover'
                  }`}
                >
                  L{level}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-semibold text-text-primary mb-1">
              Clinical Specialty
            </label>
            <Select
              value={specialty}
              onChange={(e) => setSpecialty(e.target.value)}
              className="w-full h-9 text-xs"
            >
              <option value="General Medicine">General Medicine</option>
              <option value="Cardiology">Cardiology</option>
              <option value="Neurology">Neurology</option>
              <option value="Respiratory">Respiratory</option>
              <option value="Orthopedics">Orthopedics</option>
              <option value="Emergency">Emergency</option>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-1">
            <label className="flex items-center gap-2 p-3 rounded-lg border border-border-light bg-bg-surface-hover cursor-pointer">
              <input
                type="checkbox"
                checked={isolationRequired}
                onChange={(e) => setIsolationRequired(e.target.checked)}
                className="rounded border-border-medium text-brand-primary"
              />
              <span className="font-medium text-text-primary">Isolation Required</span>
            </label>
            <label className="flex items-center gap-2 p-3 rounded-lg border border-border-light bg-bg-surface-hover cursor-pointer">
              <input
                type="checkbox"
                checked={ventilatorRequired}
                onChange={(e) => setVentilatorRequired(e.target.checked)}
                className="rounded border-border-medium text-brand-primary"
              />
              <span className="font-medium text-text-primary">Ventilator Required</span>
            </label>
          </div>
        </form>
      </Dialog>

      {/* Transfer Patient Modal */}
      {transferPatient && (
        <Dialog
          isOpen={!!transferPatient}
          onClose={() => setTransferPatient(null)}
          title={`Transfer Patient — ${transferPatient.patient_id}`}
          description="Select an available destination bed. The current bed will move to CLEANING."
          maxWidth="sm"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setTransferPatient(null)}
                disabled={transferMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                type="submit"
                form="patient-transfer-form"
                isLoading={transferMutation.isPending}
                disabled={!destinationBedId}
                leftIcon={<ArrowLeftRight className="w-3.5 h-3.5" />}
              >
                Confirm Transfer
              </Button>
            </div>
          }
        >
          <form id="patient-transfer-form" onSubmit={handleTransferSubmit} className="space-y-4 text-xs">
            {availableBeds.length === 0 ? (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-300">
                No available beds are currently ready for transfer.
              </div>
            ) : (
              <div>
                <label className="block font-semibold text-text-primary mb-1.5">
                  Destination Bed
                </label>
                <Select
                  value={destinationBedId}
                  onChange={(e) => setDestinationBedId(e.target.value)}
                  className="w-full h-9 text-xs"
                >
                  {availableBeds.map((b) => (
                    <option key={b.bed_id} value={b.bed_id}>
                      {b.bed_id} — {b.ward} ({b.bed_type})
                      {b.isolation_capable ? ' [Isolation]' : ''}
                    </option>
                  ))}
                </Select>
              </div>
            )}
          </form>
        </Dialog>
      )}
    </div>
  );
};
