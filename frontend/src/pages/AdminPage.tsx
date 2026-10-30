import React from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import { Settings, Shield, Plus, Database, AlertCircle, Cpu } from 'lucide-react';

export const AdminPage: React.FC = () => {
  const notAvailableTooltip = 'Not available in the backend yet';

  const requiredEndpoints = [
    {
      method: 'POST',
      path: '/admin/beds',
      desc: 'Provision new physical beds with designated care tier and isolation capability',
    },
    {
      method: 'PATCH',
      path: '/admin/beds/{bed_id}',
      desc: 'Update bed status (e.g. set to MAINTENANCE or mark decommissioned)',
    },
    {
      method: 'POST',
      path: '/admin/staff',
      desc: 'Register clinical staff members and adjust workload shift rosters',
    },
    {
      method: 'POST',
      path: '/admin/equipment',
      desc: 'Register biomedical devices (ventilators, telemetry) and monitor locations',
    },
    {
      method: 'PUT',
      path: '/admin/policy/config',
      desc: 'Tune reinforcement learning allocation policy parameters and fallback thresholds',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospital Administration & Configuration"
        description="Administrative controls for physical bed capacity, clinical staffing parameters, and decision policy weighting."
        badge={
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-700 dark:text-slate-300 border border-slate-500/20">
            <Settings className="w-3 h-3" />
            Administrative Portal
          </span>
        }
      />

      {/* Architecture Notice Banner */}
      <div className="p-4 bg-bg-surface border border-border-light rounded-xl space-y-2 text-xs">
        <div className="flex items-center gap-2 text-text-primary font-semibold">
          <Database className="w-4 h-4 text-brand-primary flex-shrink-0" />
          <span>Hospital Topology Notice</span>
        </div>
        <p className="text-text-muted leading-relaxed">
          Physical hospital infrastructure (wards, beds, biomedical equipment, and clinician rosters) is currently configured via backend seed scripts and database migrations. Interactive administrative mutations require dedicated REST API endpoints.
        </p>
      </div>

      {/* Proposed Administrative Endpoints Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary flex items-center gap-2">
              <Shield className="w-4 h-4 text-brand-primary" />
              Required Backend Administrative Endpoints
            </CardTitle>
            <span className="text-xs text-text-muted">RFC Specification</span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {requiredEndpoints.map((ep, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl border border-border-light bg-bg-surface-hover/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-brand-primary text-white">
                      {ep.method}
                    </span>
                    <span className="font-mono font-semibold text-text-primary">
                      {ep.path}
                    </span>
                  </div>
                  <p className="text-text-muted text-[11px]">{ep.desc}</p>
                </div>

                <Tooltip content={notAvailableTooltip}>
                  <div>
                    <Button variant="outline" size="sm" disabled leftIcon={<Plus className="w-3.5 h-3.5" />}>
                      Configure
                    </Button>
                  </div>
                </Tooltip>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* RL Policy Tuning Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-primary" />
            Reinforcement Learning Policy Tuning
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-4 rounded-xl border border-dashed border-border-medium bg-bg-page/50 space-y-4 text-xs">
            <div className="flex items-center gap-2 text-text-muted">
              <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
              <span>
                Hyperparameter adjustment (entropy coefficient, reward weights for wait time vs bed turnover) is executed offline during agent training in the <code>rl/</code> pipeline.
              </span>
            </div>

            <div className="flex items-center gap-3">
              <Tooltip content={notAvailableTooltip}>
                <div>
                  <Button variant="outline" size="sm" disabled>
                    Retrain PPO Policy
                  </Button>
                </div>
              </Tooltip>

              <Tooltip content={notAvailableTooltip}>
                <div>
                  <Button variant="outline" size="sm" disabled>
                    Deploy New Policy Weights
                  </Button>
                </div>
              </Tooltip>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
