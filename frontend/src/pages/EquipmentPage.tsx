import React, { useState, useMemo } from 'react';
import {
  useEquipment,
  usePatients,
  useAssignEquipment,
  useReleaseEquipment,
  getErrorMessage,
} from '@/api/hooks';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { useToast } from '@/components/feedback/Toast';
import { StatusDot } from '@/components/domain/StatusDot';
import { Select, Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Equipment } from '@/api/schemas';
import { Stethoscope, Wind, Activity, Wrench, RefreshCw, Search, Link2, Unlink } from 'lucide-react';

export const EquipmentPage: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const { data, isLoading, error, refetch } = useEquipment();
  const { data: patientsData } = usePatients();
  const assignMutation = useAssignEquipment();
  const releaseMutation = useReleaseEquipment();

  const canManageEquipment =
    user?.role === 'admin' || user?.role === 'nurse' || user?.role === 'doctor';

  const [typeFilter, setTypeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchLocation, setSearchLocation] = useState('');
  const [assigningItem, setAssigningItem] = useState<Equipment | null>(null);
  const [selectedPatientId, setSelectedPatientId] = useState('');

  const admittedPatients = useMemo(
    () => (patientsData || []).filter((p) => p.current_status === 'ADMITTED'),
    [patientsData]
  );

  const equipment: Equipment[] = useMemo(() => data || [], [data]);

  // Filter equipment
  const filteredEquipment = useMemo(() => {
    return equipment.filter((eq) => {
      if (typeFilter !== 'ALL' && eq.type !== typeFilter) return false;
      if (statusFilter !== 'ALL' && eq.status !== statusFilter) return false;
      if (
        searchLocation &&
        !eq.location.toLowerCase().includes(searchLocation.toLowerCase()) &&
        !eq.equipment_id.toLowerCase().includes(searchLocation.toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [equipment, typeFilter, statusFilter, searchLocation]);

  // Statistics
  const total = equipment.length;
  const available = equipment.filter((e) => e.status === 'AVAILABLE').length;
  const inUse = equipment.filter((e) => e.status === 'IN_USE').length;
  const maintenance = equipment.filter((e) => e.status === 'MAINTENANCE').length;

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Equipment & Telemetry"
          description="Inventory tracking for ventilators, telemetry units, and diagnostic apparatus."
        />
        <TableSkeleton rows={8} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Equipment & Telemetry"
          description="Inventory tracking for ventilators, telemetry units, and diagnostic apparatus."
        />
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Clinical Equipment & Telemetry"
        description="Inventory tracking for ventilators, telemetry units, and diagnostic apparatus."
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
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">Total Inventory</span>
          <div className="text-2xl font-bold font-mono text-text-primary mt-1">{total}</div>
          <span className="text-[11px] text-text-muted">Registered hospital units</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">Available</span>
          <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {available}
          </div>
          <span className="text-[11px] text-text-muted">Ready for deployment</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">In Active Use</span>
          <div className="text-2xl font-bold font-mono text-sky-600 dark:text-sky-400 mt-1">
            {inUse}
          </div>
          <span className="text-[11px] text-text-muted">Attached to patient beds</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">In Maintenance</span>
          <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400 mt-1">
            {maintenance}
          </div>
          <span className="text-[11px] text-text-muted">Servicing / Calibration</span>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 bg-bg-surface border border-border-light rounded-xl shadow-card text-xs">
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <Select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Equipment Types</option>
            <option value="VENTILATOR">Mechanical Ventilators</option>
            <option value="TELEMETRY">Telemetry Monitors</option>
            <option value="DIAGNOSTIC">Diagnostic Devices</option>
          </Select>

          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Statuses</option>
            <option value="AVAILABLE">Available</option>
            <option value="IN_USE">In Use</option>
            <option value="MAINTENANCE">Under Maintenance</option>
          </Select>
        </div>

        <div className="w-full sm:w-64">
          <Input
            placeholder="Search by ID or Location..."
            value={searchLocation}
            onChange={(e) => setSearchLocation(e.target.value)}
            leftIcon={<Search className="w-3.5 h-3.5 text-text-muted" />}
            className="h-8 text-xs"
          >
          </Input>
        </div>
      </div>

      {/* Equipment Table */}
      <div className="bg-bg-surface border border-border-light rounded-xl shadow-card overflow-hidden">
        {filteredEquipment.length === 0 ? (
          <EmptyState
            title="No equipment found"
            description="Try modifying search or filter criteria."
            icon={<Stethoscope className="w-8 h-8 text-text-muted" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-bg-page/75 border-b border-border-light text-text-muted uppercase text-[11px] font-semibold tracking-wider">
                  <th className="p-3.5">Device ID</th>
                  <th className="p-3.5">Equipment Type</th>
                  <th className="p-3.5">Assigned Location</th>
                  <th className="p-3.5">Operational Status</th>
                  {canManageEquipment && <th className="p-3.5 text-right">Action</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light/60">
                {filteredEquipment.map((item: Equipment) => {
                  const typeIcon: Record<string, React.ReactNode> = {
                    VENTILATOR: <Wind className="w-3.5 h-3.5 text-indigo-500" />,
                    TELEMETRY: <Activity className="w-3.5 h-3.5 text-sky-500" />,
                    DIAGNOSTIC: <Wrench className="w-3.5 h-3.5 text-emerald-500" />,
                  };

                  const statusClass: Record<string, string> = {
                    AVAILABLE: 'text-emerald-600 dark:text-emerald-400 font-semibold',
                    IN_USE: 'text-sky-600 dark:text-sky-400 font-semibold',
                    MAINTENANCE: 'text-amber-600 dark:text-amber-400 font-semibold',
                  };

                  return (
                    <tr key={item.equipment_id} className="hover:bg-bg-surface-hover/70">
                      <td className="p-3.5 font-mono font-bold text-brand-primary">
                        {item.equipment_id}
                      </td>
                      <td className="p-3.5">
                        <span className="inline-flex items-center gap-1.5 font-medium text-text-primary">
                          {typeIcon[item.type] || <Stethoscope className="w-3.5 h-3.5 text-slate-500" />}
                          {item.type}
                        </span>
                      </td>
                      <td className="p-3.5 text-text-secondary font-medium">
                        {item.location}
                      </td>
                      <td className="p-3.5">
                        <span className="inline-flex items-center gap-2">
                          <StatusDot status={item.status} />
                          <span className={statusClass[item.status] || 'text-slate-600'}>{item.status}</span>
                        </span>
                      </td>
                      {canManageEquipment && (
                        <td className="p-3.5 text-right">
                          {item.status === 'AVAILABLE' && (
                            <Button
                              size="sm"
                              variant="outline"
                              leftIcon={<Link2 className="w-3 h-3" />}
                              onClick={() => {
                                setAssigningItem(item);
                                setSelectedPatientId(admittedPatients[0]?.patient_id ?? '');
                              }}
                            >
                              Assign
                            </Button>
                          )}
                          {item.status === 'IN_USE' && (
                            <Button
                              size="sm"
                              variant="secondary"
                              leftIcon={<Unlink className="w-3 h-3" />}
                              isLoading={
                                releaseMutation.isPending &&
                                releaseMutation.variables?.equipment_id === item.equipment_id
                              }
                              onClick={() => {
                                releaseMutation.mutate(
                                  { equipment_id: item.equipment_id },
                                  {
                                    onSuccess: () => {
                                      showToast({
                                        type: 'success',
                                        title: 'Equipment Released',
                                        message: `${item.equipment_id} is now AVAILABLE.`,
                                      });
                                    },
                                    onError: (err) => {
                                      showToast({
                                        type: 'error',
                                        title: 'Release Failed',
                                        message: getErrorMessage(err),
                                      });
                                    },
                                  }
                                );
                              }}
                            >
                              Release
                            </Button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Assign Equipment Dialog */}
      {assigningItem && (
        <Dialog
          isOpen={!!assigningItem}
          onClose={() => setAssigningItem(null)}
          title={`Assign Equipment — ${assigningItem.equipment_id}`}
          description={`Type: ${assigningItem.type} • Current Location: ${assigningItem.location}`}
          maxWidth="sm"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setAssigningItem(null)}
                disabled={assignMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={assignMutation.isPending}
                disabled={!selectedPatientId}
                onClick={() => {
                  assignMutation.mutate(
                    {
                      equipment_id: assigningItem.equipment_id,
                      patient_id: selectedPatientId,
                    },
                    {
                      onSuccess: () => {
                        showToast({
                          type: 'success',
                          title: 'Equipment Assigned',
                          message: `${assigningItem.equipment_id} assigned to ${selectedPatientId}.`,
                        });
                        setAssigningItem(null);
                      },
                      onError: (err) => {
                        showToast({
                          type: 'error',
                          title: 'Assignment Failed',
                          message: getErrorMessage(err),
                        });
                      },
                    }
                  );
                }}
              >
                Confirm Assignment
              </Button>
            </div>
          }
        >
          <div className="space-y-3 text-xs">
            {admittedPatients.length === 0 ? (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-300">
                No admitted patients currently available for equipment assignment.
              </div>
            ) : (
              <div>
                <label className="block font-semibold text-text-primary mb-1.5">
                  Select Admitted Patient
                </label>
                <Select
                  value={selectedPatientId}
                  onChange={(e) => setSelectedPatientId(e.target.value)}
                  className="w-full h-9 text-xs"
                >
                  {admittedPatients.map((p) => (
                    <option key={p.patient_id} value={p.patient_id}>
                      {p.patient_id} — {p.specialty} (Acuity L{p.acuity})
                    </option>
                  ))}
                </Select>
              </div>
            )}
          </div>
        </Dialog>
      )}
    </div>
  );
};
