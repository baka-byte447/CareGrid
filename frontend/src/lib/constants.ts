/**
 * constants.ts — Single source of truth for all labels and configuration.
 *
 * No other file defines these values. All components import from here.
 */

export type AcuityLevel = 1 | 2 | 3 | 4 | 5

/** Acuity level labels (1 = least urgent, 5 = critical) */
export const ACUITY_LABELS: Record<AcuityLevel, { label: string; description: string }> = {
  1: { label: 'Non-urgent', description: 'Minor symptoms, stable' },
  2: { label: 'Less Urgent', description: 'Moderate distress, stable vitals' },
  3: { label: 'Urgent', description: 'Potential acute risk, requires monitoring' },
  4: { label: 'Emergent', description: 'Severe condition, organ threat' },
  5: { label: 'Critical', description: 'Immediate resuscitation required' },
}

/** Ward ordering list for display (ICU first) */
export const WARD_TYPE_LIST = ['ICU', 'STEP_DOWN', 'WARD'] as const

/** Ward ordering for display (ICU first) */
export const WARD_TYPE_ORDER: Record<string, number> = {
  ICU: 0,
  STEP_DOWN: 1,
  WARD: 2,
}

/** Human-readable ward type labels */
export const WARD_TYPE_LABELS: Record<string, string> = {
  ICU: 'ICU',
  STEP_DOWN: 'Step-Down',
  WARD: 'General Ward',
}

/** Bed status display */
export const BED_STATUS_LABELS: Record<string, string> = {
  AVAILABLE: 'Available',
  OCCUPIED: 'Occupied',
  CLEANING: 'Cleaning',
}

/** Equipment type labels */
export const EQUIPMENT_TYPE_LABELS: Record<string, string> = {
  VENTILATOR: 'Ventilator',
  TELEMETRY: 'Telemetry',
  DIAGNOSTIC: 'Diagnostic',
}

/** Staff role labels */
export const STAFF_ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  'Critical-care': { bg: '#fef2f2', text: '#dc2626' },
  Emergency: { bg: '#fff7ed', text: '#f97316' },
  General: { bg: '#f0fdf4', text: '#16a34a' },
}

/**
 * Surge scenario presets.
 * NOTE: No `/surge/presets` endpoint exists. Multipliers are documented
 * in the build prompt (1.0, 1.6, 2.7). Duration is set to 24h as default.
 * Label: "Simulation presets — defined in frontend constants, no backend presets endpoint"
 */
export const SURGE_PRESETS = [
  {
    id: 'normal',
    name: 'Normal load',
    label: 'Normal load',
    arrival_rate_multiplier: 1.0,
    duration_hours: 24,
    description: 'Standard baseline operational load (1.0x arrival rate)',
  },
  {
    id: 'moderate_flu',
    name: 'Moderate surge (×1.6)',
    label: 'Moderate surge (×1.6)',
    arrival_rate_multiplier: 1.6,
    duration_hours: 24,
    description: 'Seasonal outbreak with elevated admission demand (1.6x)',
  },
  {
    id: 'mass_casualty',
    name: 'Mass-casualty (×2.7)',
    label: 'Mass-casualty (×2.7)',
    arrival_rate_multiplier: 2.7,
    duration_hours: 24,
    description: 'Major regional incident or pandemic peak volume (2.7x)',
  },
] as const

export type SurgePreset = (typeof SURGE_PRESETS)[number]

/** Auto-refresh interval for Command Centre and Queue (30 seconds) */
export const COMMAND_CENTRE_POLL_MS = 30_000

/** Stale data banner threshold (2 minutes) */
export const STALE_THRESHOLD_MS = 120_000
