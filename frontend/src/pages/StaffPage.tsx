import React, { useState, useMemo } from 'react';
import { useStaff } from '@/api/hooks';
import { PageHeader } from '@/components/layout/PageHeader';
import { TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Select } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Staff } from '@/api/schemas';
import { UserCheck, RefreshCw, AlertCircle, Shield } from 'lucide-react';

export const StaffPage: React.FC = () => {
  const { data, isLoading, error, refetch } = useStaff();

  const [roleFilter, setRoleFilter] = useState('ALL');
  const [shiftFilter, setShiftFilter] = useState('ALL');
  const [skillFilter, setSkillFilter] = useState('ALL');

  const staff: Staff[] = useMemo(() => data || [], [data]);

  // Extract unique roles and shifts
  const roles = useMemo(() => {
    const set = new Set<string>();
    staff.forEach((s: Staff) => set.add(s.role));
    return Array.from(set).sort();
  }, [staff]);

  const shifts = useMemo(() => {
    const set = new Set<string>();
    staff.forEach((s: Staff) => set.add(s.shift));
    return Array.from(set).sort();
  }, [staff]);

  // Filtered staff
  const filteredStaff = useMemo(() => {
    return staff.filter((s: Staff) => {
      if (roleFilter !== 'ALL' && s.role !== roleFilter) return false;
      if (shiftFilter !== 'ALL' && s.shift !== shiftFilter) return false;
      if (skillFilter !== 'ALL' && s.skill_level !== skillFilter) return false;
      return true;
    });
  }, [staff, roleFilter, shiftFilter, skillFilter]);

  // Compute metrics
  const totalStaff = staff.length;
  const avgWorkload =
    totalStaff > 0 ? staff.reduce((acc: number, s: Staff) => acc + s.workload, 0) / totalStaff : 0;
  const highWorkloadCount = staff.filter((s: Staff) => s.workload >= 80).length;

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Staff & Rosters"
          description="Monitoring clinical staff allocation, shift duties, and workload capacity."
        />
        <TableSkeleton rows={8} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Staff & Rosters"
          description="Monitoring clinical staff allocation, shift duties, and workload capacity."
        />
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Clinical Staff & Rosters"
        description="Monitoring clinical staff allocation, shift duties, and workload capacity."
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">Active Roster</span>
          <div className="text-2xl font-bold font-mono text-text-primary mt-1">{totalStaff}</div>
          <span className="text-[11px] text-text-muted">Physicians and nursing staff</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">Mean Workload</span>
          <div className="text-2xl font-bold font-mono text-brand-primary mt-1">
            {avgWorkload.toFixed(0)}%
          </div>
          <span className="text-[11px] text-text-muted">Across all departments</span>
        </div>
        <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
          <span className="text-xs text-text-muted uppercase font-semibold">High Workload (&ge;80%)</span>
          <div className="text-2xl font-bold font-mono text-red-600 dark:text-red-400 mt-1">
            {highWorkloadCount}
          </div>
          <span className="text-[11px] text-text-muted">Staff nearing peak capacity</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-bg-surface border border-border-light rounded-xl shadow-card text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Roles</option>
            {roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>

          <Select
            value={shiftFilter}
            onChange={(e) => setShiftFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Shifts</option>
            {shifts.map((s) => (
              <option key={s} value={s}>
                {s} Shift
              </option>
            ))}
          </Select>

          <Select
            value={skillFilter}
            onChange={(e) => setSkillFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Skill Levels</option>
            <option value="SENIOR">Senior</option>
            <option value="MID">Mid-Level</option>
            <option value="JUNIOR">Junior</option>
          </Select>
        </div>

        <div className="text-text-muted">
          Showing <strong>{filteredStaff.length}</strong> of {totalStaff} clinicians
        </div>
      </div>

      {/* Staff Table */}
      <div className="bg-bg-surface border border-border-light rounded-xl shadow-card overflow-hidden">
        {filteredStaff.length === 0 ? (
          <EmptyState
            title="No staff found"
            description="Adjust active filters to view clinical roster."
            icon={<UserCheck className="w-8 h-8 text-text-muted" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-bg-page/75 border-b border-border-light text-text-muted uppercase text-[11px] font-semibold tracking-wider">
                  <th className="p-3.5">Staff ID</th>
                  <th className="p-3.5">Role</th>
                  <th className="p-3.5">Skill Level</th>
                  <th className="p-3.5">Shift</th>
                  <th className="p-3.5 w-48">Workload Capacity</th>
                  <th className="p-3.5 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light/60">
                {filteredStaff.map((member) => {
                  const isOverloaded = member.workload >= 80;
                  return (
                    <tr key={member.staff_id} className="hover:bg-bg-surface-hover/70">
                      <td className="p-3.5 font-mono font-bold text-brand-primary">
                        {member.staff_id}
                      </td>
                      <td className="p-3.5 font-medium text-text-primary">
                        {member.role}
                      </td>
                      <td className="p-3.5">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-bg-page border border-border-light text-text-secondary">
                          <Shield className="w-3 h-3 text-brand-primary" />
                          {member.skill_level}
                        </span>
                      </td>
                      <td className="p-3.5 text-text-secondary">
                        {member.shift}
                      </td>
                      <td className="p-3.5">
                        <div className="space-y-1">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-text-muted">Load</span>
                            <span className={`font-mono font-bold ${isOverloaded ? 'text-red-600 dark:text-red-400' : 'text-text-primary'}`}>
                              {member.workload}%
                            </span>
                          </div>
                          <div className="w-full h-2 rounded-full bg-border-light dark:bg-border-medium/30 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${
                                isOverloaded
                                  ? 'bg-red-500'
                                  : member.workload > 50
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(member.workload, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="p-3.5 text-right">
                        {isOverloaded ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-red-600 dark:text-red-400">
                            <AlertCircle className="w-3.5 h-3.5" />
                            Overburdened
                          </span>
                        ) : (
                          <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                            Nominal
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
