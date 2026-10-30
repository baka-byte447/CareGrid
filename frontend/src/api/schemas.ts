/**
 * schemas.ts — Zod schemas validating every API response at the boundary.
 *
 * Source of truth: backend/api/main.py + SQLAlchemy models.
 * Field names match exactly what main.py returns.
 * On validation failure the hooks show "Unexpected response from server".
 */

import { z } from 'zod'

// ─── Patient ────────────────────────────────────────────────────────────────
export const PatientSchema = z.object({
  patient_id: z.string(),
  age_group: z.string(),
  acuity: z.number().int().min(1).max(5),
  specialty: z.string(),
  predicted_los: z.number(),
  isolation_required: z.boolean(),
  ventilator_required: z.boolean(),
  // Simulated arrival time — ISO 8601 string (NOT compared to Date.now())
  arrival_time: z.string(),
  current_status: z.enum(['WAITING', 'ADMITTED']),
})

export const PatientsResponseSchema = z.object({
  patients: z.array(PatientSchema),
})

// ─── Bed ────────────────────────────────────────────────────────────────────
export const BedSchema = z.object({
  bed_id: z.string(),
  bed_type: z.enum(['ICU', 'STEP_DOWN', 'WARD']),
  ward: z.string(),
  // Backend may return AVAILABLE, OCCUPIED, or CLEANING
  status: z.string(),
  isolation_capable: z.boolean(),
})

export const BedsResponseSchema = z.object({
  beds: z.array(BedSchema),
})

// ─── Staff ──────────────────────────────────────────────────────────────────
export const StaffSchema = z.object({
  staff_id: z.string(),
  role: z.string(),
  skill_level: z.string(),
  shift: z.string(),
  workload: z.number().int(),
})

export const StaffResponseSchema = z.object({
  staff: z.array(StaffSchema),
})

// ─── Equipment ──────────────────────────────────────────────────────────────
export const EquipmentSchema = z.object({
  equipment_id: z.string(),
  type: z.string(),
  status: z.string(),
  location: z.string(),
})

export const EquipmentResponseSchema = z.object({
  equipment: z.array(EquipmentSchema),
})

// ─── Metrics ────────────────────────────────────────────────────────────────
// Source: backend/api/main.py get_metrics() — NOT api_contract.md (which is wrong)
export const MetricsResponseSchema = z.object({
  patients_total: z.number().int(),
  patients_waiting: z.number().int(),
  patients_admitted: z.number().int(),
  beds_total: z.number().int(),
  beds_available: z.number().int(),
  beds_occupied: z.number().int(),
  bed_occupancy_rate: z.number(),
  ventilators_total: z.number().int(),
  ventilators_available: z.number().int(),
  ventilators_in_use: z.number().int(),
  approved_allocations: z.number().int(),
})

// ─── Audit Log ──────────────────────────────────────────────────────────────
export const AuditEntrySchema = z.object({
  patient_id: z.string(),
  bed_id: z.string().nullable(),
  action: z.string(),
  algorithm: z.string(),
  // Real server UTC timestamp — not a simulated time
  timestamp: z.string(),
})

export const AuditResponseSchema = z.object({
  audit: z.array(AuditEntrySchema),
})

// ─── Allocation Recommend ────────────────────────────────────────────────────
export const RecommendResponseSchema = z.object({
  patient_id: z.string(),
  recommended_bed_id: z.string().nullable(),
  algorithm: z.string(),
  reason: z.string(),
  status: z.enum(['RECOMMENDED', 'NO_SUITABLE_BED']),
})

// ─── Allocation Approve ──────────────────────────────────────────────────────
export const ApproveResponseSchema = z.object({
  patient_id: z.string(),
  bed_id: z.string(),
  status: z.literal('APPROVED'),
})

// ─── Surge Simulate ─────────────────────────────────────────────────────────
// Source: backend/api/main.py simulate_surge() + simulator/metrics/summary.py
const SurgeMetricsSchema = z.object({
  patients_total: z.number().int(),
  patients_admitted: z.number().int(),
  patients_discharged: z.number().int(),
  patients_still_waiting: z.number().int(),
  avg_wait_min: z.number(),
  median_wait_min: z.number(),
  avg_wait_incl_unadmitted_min: z.number(),
  p90_wait_incl_unadmitted_min: z.number(),
  p90_wait_min: z.number(),
  max_wait_min: z.number(),
  avg_wait_by_acuity_min: z.record(z.string(), z.number().nullable()),
  pct_admitted_within_60min: z.number(),
  icu_utilization: z.number().nullable(),
  step_down_utilization: z.number().nullable(),
  ward_utilization: z.number().nullable(),
  overall_bed_utilization: z.number(),
  ventilator_utilization: z.number().nullable(),
  bed_turnover_per_bed_per_day: z.number(),
  peak_waiting_queue: z.number().int(),
  constraint_violations: z.number().int(),
  measurement_window_hours: z.number(),
  waiting_patients_elapsed_wait_min: z.object({
    avg: z.number(),
    max: z.number(),
  }),
})

export const SurgeResponseSchema = z.object({
  status: z.literal('COMPLETED'),
  arrival_rate_multiplier: z.number(),
  duration_hours: z.number().int(),
  patients_arrived: z.number().int(),
  simulation_start: z.string(),
  simulation_end: z.string(),
  metrics: SurgeMetricsSchema,
})

// ─── Type exports ────────────────────────────────────────────────────────────
export type Patient = z.infer<typeof PatientSchema>
export type Bed = z.infer<typeof BedSchema>
export type BedType = 'ICU' | 'STEP_DOWN' | 'WARD'
export type Staff = z.infer<typeof StaffSchema>
export type Equipment = z.infer<typeof EquipmentSchema>
export type Metrics = z.infer<typeof MetricsResponseSchema>
export type AuditEntry = z.infer<typeof AuditEntrySchema>
export type RecommendResponse = z.infer<typeof RecommendResponseSchema>
export type ApproveResponse = z.infer<typeof ApproveResponseSchema>
export type SurgeResponse = z.infer<typeof SurgeResponseSchema>
export type SurgeMetrics = z.infer<typeof SurgeMetricsSchema>
