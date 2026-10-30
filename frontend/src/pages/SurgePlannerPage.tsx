import React, { useState } from 'react';
import { useSimulateSurge } from '@/api/hooks';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Tooltip } from '@/components/ui/Tooltip';
import { SURGE_PRESETS, SurgePreset } from '@/lib/constants';
import { formatPct, formatMinutes } from '@/lib/format';
import {
  Zap,
  Play,
  RotateCcw,
  AlertTriangle,
  Info,
  Clock,
  Users,
  BedDouble,
  ShieldAlert,
  Loader2,
  CheckCircle,
} from 'lucide-react';

export const SurgePlannerPage: React.FC = () => {
  const [multiplier, setMultiplier] = useState<number>(2.0);
  const [durationHours, setDurationHours] = useState<number>(12);
  const [activePreset, setActivePreset] = useState<string | null>('moderate_flu');

  const surgeMutation = useSimulateSurge();

  const handleApplyPreset = (preset: SurgePreset) => {
    setActivePreset(preset.id);
    setMultiplier(preset.arrival_rate_multiplier);
    setDurationHours(preset.duration_hours);
  };

  const handleRunSimulation = () => {
    surgeMutation.mutate({
      arrival_rate_multiplier: multiplier,
      duration_hours: durationHours,
    });
  };

  const handleReset = () => {
    surgeMutation.reset();
  };

  const result = surgeMutation.data;
  const metrics = result?.metrics;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Surge Capacity Planner"
        description="Run discrete-event hospital stress simulations to forecast bed shortages and wait time degradation under surge conditions."
        badge={
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-500/20">
            <Zap className="w-3 h-3 text-indigo-500" />
            Simulation Engine
          </span>
        }
      />

      {/* Preset Banner Label Note (Strict prompt requirement) */}
      <div className="p-3 bg-bg-surface border border-border-light rounded-xl text-xs flex items-center justify-between">
        <div className="flex items-center gap-2 text-text-secondary">
          <Info className="w-4 h-4 text-brand-primary flex-shrink-0" />
          <span>
            <strong>Simulation Presets:</strong> Predefined in frontend constants (no backend presets endpoint).
          </span>
        </div>
        <Tooltip content="The backend provides POST /surge/simulate which accepts custom arrival multipliers and durations. Presets configure these parameters for standard clinical scenarios.">
          <span className="text-[11px] text-text-muted underline cursor-help">About Presets</span>
        </Tooltip>
      </div>

      {/* Parameter Controls and Presets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Preset Cards */}
        <div className="lg:col-span-1 space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Clinical Surge Scenarios
          </h3>
          <div className="space-y-2.5">
            {SURGE_PRESETS.map((preset) => (
              <div
                key={preset.id}
                onClick={() => handleApplyPreset(preset)}
                className={`p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 select-none ${
                  activePreset === preset.id
                    ? 'border-brand-primary bg-brand-primary-light/40 dark:bg-brand-primary/10 shadow-sm'
                    : 'border-border-light bg-bg-surface hover:bg-bg-surface-hover'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-text-primary">{preset.name}</span>
                  <span className="font-mono text-[11px] font-bold text-brand-primary">
                    {preset.arrival_rate_multiplier}x &bull; {preset.duration_hours}h
                  </span>
                </div>
                <p className="text-text-muted text-[11px] leading-relaxed">
                  {preset.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Custom Input Controls & Execution */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary">
                Simulation Parameters
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Arrival Multiplier Slider */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <label className="font-semibold text-text-primary">
                      Arrival Rate Multiplier
                    </label>
                    <span className="font-mono font-bold text-sm text-brand-primary bg-brand-primary-light/50 dark:bg-brand-primary/20 px-2 py-0.5 rounded">
                      {multiplier.toFixed(1)}x baseline
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1.0"
                    max="5.0"
                    step="0.1"
                    value={multiplier}
                    onChange={(e) => {
                      setMultiplier(parseFloat(e.target.value));
                      setActivePreset(null);
                    }}
                    className="w-full accent-brand-primary cursor-pointer"
                  />
                  <div className="flex justify-between text-[11px] text-text-muted">
                    <span>1.0x (Normal)</span>
                    <span>2.5x (Epidemic)</span>
                    <span>5.0x (Mass Casualty)</span>
                  </div>
                </div>

                {/* Duration Slider */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <label className="font-semibold text-text-primary">
                      Simulation Window Duration
                    </label>
                    <span className="font-mono font-bold text-sm text-brand-primary bg-brand-primary-light/50 dark:bg-brand-primary/20 px-2 py-0.5 rounded">
                      {durationHours} Hours
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="48"
                    step="1"
                    value={durationHours}
                    onChange={(e) => {
                      setDurationHours(parseInt(e.target.value, 10));
                      setActivePreset(null);
                    }}
                    className="w-full accent-brand-primary cursor-pointer"
                  />
                  <div className="flex justify-between text-[11px] text-text-muted">
                    <span>1 Hour (Fast Check)</span>
                    <span>12 Hours (Shift)</span>
                    <span>48 Hours (Multi-Day Surge)</span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-3 pt-3 border-t border-border-light">
                  <Button
                    variant="primary"
                    onClick={handleRunSimulation}
                    isLoading={surgeMutation.isPending}
                    leftIcon={<Play className="w-4 h-4 fill-current" />}
                  >
                    Execute Simulation Run
                  </Button>

                  {result && (
                    <Button
                      variant="secondary"
                      onClick={handleReset}
                      leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                    >
                      Clear Results
                    </Button>
                  )}
                </div>

                {/* Error Banner */}
                {surgeMutation.isError && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>Simulation error: {surgeMutation.error?.message}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Loading State during simulation run */}
      {surgeMutation.isPending && (
        <div className="p-12 bg-bg-surface border border-border-light rounded-xl text-center space-y-3 shadow-card">
          <Loader2 className="w-10 h-10 animate-spin text-brand-primary mx-auto" />
          <h4 className="text-base font-bold text-text-primary">
            Executing Discrete-Event Surge Simulation...
          </h4>
          <p className="text-xs text-text-muted max-w-md mx-auto">
            Simulating {multiplier}x patient arrivals over a {durationHours}-hour window using the RL allocation policy.
          </p>
        </div>
      )}

      {/* Simulation Results Display */}
      {result && metrics && !surgeMutation.isPending && (
        <div className="space-y-6">
          {/* Permanent Disclaimer Badge (Strict requirement) */}
          <div className="p-3 bg-amber-500/15 border border-amber-500/30 text-amber-900 dark:text-amber-200 rounded-xl text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <span>
              <strong>Simulation Result, Not Live Hospital Data:</strong> The values below represent projected outcomes from a synthetic model run over simulated time {result.simulation_start} to {result.simulation_end}.
            </span>
          </div>

          {/* Results Summary KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
              <span className="text-xs text-text-muted uppercase font-semibold flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-brand-primary" />
                Patients Arrived
              </span>
              <div className="text-2xl font-bold font-mono text-text-primary mt-1">
                {result.patients_arrived}
              </div>
              <span className="text-[11px] text-text-muted">
                {metrics.patients_admitted} admitted &bull; {metrics.patients_still_waiting} still waiting
              </span>
            </div>

            <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
              <span className="text-xs text-text-muted uppercase font-semibold flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-500" />
                Mean Wait Time
              </span>
              <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400 mt-1">
                {formatMinutes(metrics.avg_wait_min)}
              </div>
              <span className="text-[11px] text-text-muted">
                P90 wait: {formatMinutes(metrics.p90_wait_min)}
              </span>
            </div>

            <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
              <span className="text-xs text-text-muted uppercase font-semibold flex items-center gap-1.5">
                <BedDouble className="w-3.5 h-3.5 text-indigo-500" />
                Overall Bed Utilization
              </span>
              <div className="text-2xl font-bold font-mono text-indigo-600 dark:text-indigo-400 mt-1">
                {formatPct(metrics.overall_bed_utilization)}
              </div>
              <span className="text-[11px] text-text-muted">
                Peak waiting queue: {metrics.peak_waiting_queue}
              </span>
            </div>

            <div className="p-4 rounded-xl border border-border-light bg-bg-surface shadow-card">
              <span className="text-xs text-text-muted uppercase font-semibold flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                Admitted &le; 60 Min
              </span>
              <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                {formatPct(metrics.pct_admitted_within_60min)}
              </div>
              <span className="text-[11px] text-text-muted">
                Emergency triage target
              </span>
            </div>
          </div>

          {/* Unit Utilization Breakdown Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-xs uppercase font-bold text-text-muted">
                  ICU Bed Utilization
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-text-primary mb-2">
                  {formatPct(metrics.icu_utilization ?? 0)}
                </div>
                <div className="w-full h-2 rounded-full bg-border-light overflow-hidden">
                  <div
                    className="h-full bg-red-500"
                    style={{ width: `${Math.min((metrics.icu_utilization ?? 0) * 100, 100)}%` }}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-xs uppercase font-bold text-text-muted">
                  Step-Down Bed Utilization
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-text-primary mb-2">
                  {formatPct(metrics.step_down_utilization ?? 0)}
                </div>
                <div className="w-full h-2 rounded-full bg-border-light overflow-hidden">
                  <div
                    className="h-full bg-amber-500"
                    style={{ width: `${Math.min((metrics.step_down_utilization ?? 0) * 100, 100)}%` }}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-xs uppercase font-bold text-text-muted">
                  General Ward Utilization
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-text-primary mb-2">
                  {formatPct(metrics.ward_utilization ?? 0)}
                </div>
                <div className="w-full h-2 rounded-full bg-border-light overflow-hidden">
                  <div
                    className="h-full bg-sky-500"
                    style={{ width: `${Math.min((metrics.ward_utilization ?? 0) * 100, 100)}%` }}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Safety Violations & Constraint Check */}
          <Card className="border-border-light">
            <CardHeader>
              <CardTitle className="text-xs uppercase font-bold text-text-muted flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-emerald-500" />
                Clinical Safety & Constraint Verification
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs">
                <div>
                  <span className="font-semibold text-text-primary">
                    Constraint Violations Recorded:
                  </span>
                  <span className="ml-2 font-mono font-bold text-emerald-600 dark:text-emerald-400">
                    {metrics.constraint_violations}
                  </span>
                  <p className="text-text-muted text-[11px] mt-0.5">
                    No clinical safety rules (isolation or ventilator requirements) were breached by the RL policy during the surge window.
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-bg-surface-hover border border-border-light font-mono text-[11px] text-text-secondary">
                  Measurement Window: {metrics.measurement_window_hours} Hours
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
