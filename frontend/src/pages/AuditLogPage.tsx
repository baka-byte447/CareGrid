import React, { useState, useMemo } from 'react';
import { useAuditLog } from '@/api/hooks';
import { PageHeader } from '@/components/layout/PageHeader';
import { TableSkeleton } from '@/components/feedback/Skeletons';
import { ErrorState } from '@/components/feedback/ErrorState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Input, Select } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { formatServerTimestamp } from '@/lib/format';
import { AuditEntry } from '@/api/schemas';
import { ScrollText, Download, Search, RefreshCw, Cpu, Clock, CheckCircle } from 'lucide-react';

export const AuditLogPage: React.FC = () => {
  const { data, isLoading, error, refetch } = useAuditLog();

  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');
  const [algoFilter, setAlgoFilter] = useState('ALL');

  const auditEntries: AuditEntry[] = useMemo(() => data || [], [data]);

  // Extract algorithms for filter dropdown
  const algorithms = useMemo(() => {
    const set = new Set<string>();
    auditEntries.forEach((e: AuditEntry) => {
      if (e.algorithm) set.add(e.algorithm);
    });
    return Array.from(set).sort();
  }, [auditEntries]);

  // Extract actions for filter dropdown
  const actions = useMemo(() => {
    const set = new Set<string>();
    auditEntries.forEach((e: AuditEntry) => {
      if (e.action) set.add(e.action);
    });
    return Array.from(set).sort();
  }, [auditEntries]);

  // Filtered entries
  const filteredEntries = useMemo(() => {
    return auditEntries.filter((entry: AuditEntry) => {
      if (actionFilter !== 'ALL' && entry.action !== actionFilter) return false;
      if (algoFilter !== 'ALL' && entry.algorithm !== algoFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchesPatient = entry.patient_id.toLowerCase().includes(q);
        const matchesBed = entry.bed_id ? entry.bed_id.toLowerCase().includes(q) : false;
        if (!matchesPatient && !matchesBed) return false;
      }
      return true;
    });
  }, [auditEntries, actionFilter, algoFilter, searchQuery]);

  // CSV Export
  const handleExportCSV = () => {
    if (filteredEntries.length === 0) return;

    const headers = ['Timestamp (UTC)', 'Patient ID', 'Bed ID', 'Action', 'Algorithm'];
    const rows = filteredEntries.map((e: AuditEntry) => [
      `"${e.timestamp}"`,
      `"${e.patient_id}"`,
      `"${e.bed_id ?? 'N/A'}"`,
      `"${e.action}"`,
      `"${e.algorithm}"`,
    ]);

    const csvContent = [headers.join(','), ...rows.map((r: string[]) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `caregrid_audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Decision Audit Log"
          description="Immutable record of bed allocations, decision policies, and timestamped actions."
        />
        <TableSkeleton rows={8} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Clinical Decision Audit Log"
          description="Immutable record of bed allocations, decision policies, and timestamped actions."
        />
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Clinical Decision Audit Log"
        description="Immutable record of bed allocations, decision policies, and timestamped actions."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCSV}
              disabled={filteredEntries.length === 0}
              leftIcon={<Download className="w-3.5 h-3.5" />}
            >
              Export CSV
            </Button>
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

      {/* Timestamp Notice (Strict prompt requirement: Real UTC server timestamps) */}
      <div className="p-3 bg-bg-surface border border-border-light rounded-xl text-xs flex items-center justify-between">
        <div className="flex items-center gap-2 text-text-secondary">
          <Clock className="w-4 h-4 text-brand-primary flex-shrink-0" />
          <span>
            <strong>Timestamp Standard:</strong> Audit entries record actual server execution timestamps (UTC format: YYYY-MM-DD HH:MM:SS UTC).
          </span>
        </div>
        <span className="text-[11px] text-text-muted">
          Showing latest {auditEntries.length} entries (GET /audit limit: 100)
        </span>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 bg-bg-surface border border-border-light rounded-xl shadow-card text-xs">
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <div className="w-full sm:w-64">
            <Input
              placeholder="Search Patient or Bed ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<Search className="w-3.5 h-3.5 text-text-muted" />}
              className="h-8 text-xs"
            />
          </div>

          <Select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Actions ({actions.length})</option>
            {actions.map((act) => (
              <option key={act} value={act}>
                Action: {act}
              </option>
            ))}
          </Select>

          <Select
            value={algoFilter}
            onChange={(e) => setAlgoFilter(e.target.value)}
            className="text-xs h-8"
          >
            <option value="ALL">All Algorithms ({algorithms.length})</option>
            {algorithms.map((alg) => (
              <option key={alg} value={alg}>
                Policy: {alg}
              </option>
            ))}
          </Select>
        </div>

        <div className="text-text-muted text-xs">
          <strong>{filteredEntries.length}</strong> matching records
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-bg-surface border border-border-light rounded-xl shadow-card overflow-hidden">
        {filteredEntries.length === 0 ? (
          <EmptyState
            title="No audit entries found"
            description="No logged events match the active search or filter parameters."
            icon={<ScrollText className="w-8 h-8 text-text-muted" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-bg-page/75 border-b border-border-light text-text-muted uppercase text-[11px] font-semibold tracking-wider">
                  <th className="p-3.5">Server Timestamp (UTC)</th>
                  <th className="p-3.5">Action Event</th>
                  <th className="p-3.5">Patient ID</th>
                  <th className="p-3.5">Allocated Bed</th>
                  <th className="p-3.5 text-right">Governing Policy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light/60">
                {filteredEntries.map((entry, idx) => (
                  <tr key={`${entry.patient_id}-${entry.bed_id}-${entry.timestamp}-${idx}`} className="hover:bg-bg-surface-hover/70">
                    <td className="p-3.5 font-mono text-text-muted whitespace-nowrap">
                      {formatServerTimestamp(entry.timestamp)}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                        <CheckCircle className="w-3 h-3 text-emerald-600" />
                        {entry.action}
                      </span>
                    </td>
                    <td className="p-3.5 font-mono font-bold text-brand-primary">
                      {entry.patient_id}
                    </td>
                    <td className="p-3.5 font-mono font-semibold text-text-primary">
                      {entry.bed_id}
                    </td>
                    <td className="p-3.5 text-right">
                      <span className="inline-flex items-center gap-1 text-[11px] font-mono text-text-secondary bg-bg-page px-2 py-0.5 rounded border border-border-light">
                        <Cpu className="w-3 h-3 text-brand-primary" />
                        {entry.algorithm}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
