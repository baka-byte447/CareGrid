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
  current_status: z.enum(['WAITING', 'ADMITTED', 'DISCHARGED']),
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
  patient_id: z.string().nullish(),
})

export const BedsResponseSchema = z.object({
  beds: z.array(BedSchema),
})

export const BedCreateRequestSchema = BedSchema.pick({
  bed_type: true,
  isolation_capable: true,
}).extend({
  bed_id: z.string().trim().min(1).max(10),
  ward: z.string().trim().min(1).max(50),
})

export const BedCreateResponseSchema = z.object({
  message: z.string(),
  bed: BedSchema,
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
  patient_id: z.string().nullable(),
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
export type RecommendationAlgorithm = 'rule_based' | 'dqn_safe'

const SafetyBlockSchema = z.object({
  overridden: z.boolean(),
  rule_triggered: z.string().nullable().optional(),
  original_action: z.number().int(),
  reason: z.string().nullable().optional(),
})

export const RecommendResponseSchema = z.object({
  recommendation_id: z.number().int().positive(),
  patient_id: z.string(),
  recommended_bed_id: z.string().nullable(),
  algorithm: z.string(),
  reason: z.string(),
  status: z.enum(['RECOMMENDED', 'NO_SUITABLE_BED', 'WAIT']),
  safety: SafetyBlockSchema.optional(),
  q_values: z.array(z.number()).nullable().optional(),
  los_estimate_days: z.number().nullable().optional(),
  proposed_action: z.number().int().nullable().optional(),
  final_action: z.number().int().nullable().optional(),
  proposed_bed_type: z.string().nullable().optional(),
  final_bed_type: z.string().nullable().optional(),
})

// ─── Allocation Approve ──────────────────────────────────────────────────────
export const ApproveRequestSchema = z
  .object({
    recommendation_id: z.number().int().positive().optional(),
    patient_id: z.string().optional(),
    bed_id: z.string().optional(),
    encounter_id: z.number().int().optional(),
    equipment_id: z.string().optional(),
  })
  .refine(
    (data) =>
      data.recommendation_id !== undefined ||
      (Boolean(data.patient_id) && Boolean(data.bed_id)),
    {
      message: 'Either recommendation_id or both patient_id and bed_id are required',
    }
  )

export const ApproveResponseSchema = z.object({
  patient_id: z.string(),
  bed_id: z.string(),
  status: z.literal('APPROVED'),
})

export const RejectRequestSchema = z.object({
  recommendation_id: z.number().int().positive(),
  reason: z.string().trim().min(3),
})

export const RejectResponseSchema = z.object({
  recommendation_id: z.number().int().positive(),
  patient_id: z.string(),
  status: z.literal('REJECTED'),
  reason: z.string(),
})

// ─── Surge Simulate ─────────────────────────────────────────────────────────
// Source: backend/api/main.py simulate_surge() + simulator/metrics/summary.py
const ConstraintViolationsSchema = z.union([
  z.number().int(),
  z.object({
    acuity_tier: z.number().int(),
    isolation: z.number().int(),
    ventilator: z.number().int(),
    double_booking: z.number().int(),
    total: z.number().int(),
  }),
])

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
  constraint_violations: ConstraintViolationsSchema,
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
export type BedCreateRequest = z.infer<typeof BedCreateRequestSchema>
export type BedType = 'ICU' | 'STEP_DOWN' | 'WARD'
export type Staff = z.infer<typeof StaffSchema>
export type Equipment = z.infer<typeof EquipmentSchema>
export type Metrics = z.infer<typeof MetricsResponseSchema>
export type AuditEntry = z.infer<typeof AuditEntrySchema>
export type RecommendResponse = z.infer<typeof RecommendResponseSchema>
export type ApproveArgs = z.infer<typeof ApproveRequestSchema>
export type ApproveResponse = z.infer<typeof ApproveResponseSchema>
export type RejectArgs = z.infer<typeof RejectRequestSchema>
export type RejectResponse = z.infer<typeof RejectResponseSchema>
export type SurgeResponse = z.infer<typeof SurgeResponseSchema>
export type SurgeMetrics = z.infer<typeof SurgeMetricsSchema>

// ─── Patient Intake ──────────────────────────────────────────────────────────
export const PatientIntakeRequestSchema = z.object({
  patient_id: z.string().min(1).max(10).optional().nullable(),
  age_group: z.string().min(1).max(20),
  acuity: z.number().int().min(1).max(5),
  specialty: z.string().min(1).max(50),
  predicted_los: z.number().positive(),
  isolation_required: z.boolean().default(false),
  ventilator_required: z.boolean().default(false),
  arrival_time: z.string().optional().nullable(),
})
export const PatientIntakeResponseSchema = z.object({
  patient_id: z.string(),
  encounter_id: z.number().int(),
  age_group: z.string(),
  acuity: z.number().int(),
  specialty: z.string(),
  predicted_los: z.number(),
  isolation_required: z.boolean(),
  ventilator_required: z.boolean(),
  arrival_time: z.string(),
  current_status: z.string(),
  encounter_status: z.string(),
})

// ─── Patient Discharge ───────────────────────────────────────────────────────
export const DischargeRequestSchema = z.object({
  release_reason: z.string().min(1).max(100).default('discharge'),
  encounter_id: z.number().int().optional().nullable(),
})
export const DischargeResponseSchema = z.object({
  patient_id: z.string(),
  encounter_id: z.number().int(),
  bed_id: z.string(),
  bed_status: z.string(),
  released_equipment_ids: z.array(z.string()),
  patient_status: z.string(),
  encounter_status: z.string(),
  discharged_at: z.string(),
})

// ─── Patient Transfer ────────────────────────────────────────────────────────
export const TransferRequestSchema = z.object({
  destination_bed_id: z.string().min(1).max(10),
  release_reason: z.string().min(1).max(100).default('transfer'),
  encounter_id: z.number().int().optional().nullable(),
})
export const TransferResponseSchema = z.object({
  patient_id: z.string(),
  encounter_id: z.number().int(),
  from_bed_id: z.string(),
  to_bed_id: z.string(),
  status: z.string(),
})

// ─── Bed Cleaning ────────────────────────────────────────────────────────────
export const BedCleaningResponseSchema = z.object({
  bed_id: z.string(),
  status: z.string(),
})

// ─── Equipment Assign/Release ────────────────────────────────────────────────
export const EquipmentAssignRequestSchema = z.object({
  patient_id: z.string().optional().nullable(),
  encounter_id: z.number().int().optional().nullable(),
})
export const EquipmentReleaseRequestSchema = z.object({
  patient_id: z.string().optional().nullable(),
  encounter_id: z.number().int().optional().nullable(),
  release_reason: z.string().min(1).max(100).default('released'),
})
export const EquipmentAssignmentResponseSchema = z.object({
  assignment_id: z.number().int(),
  encounter_id: z.number().int(),
  patient_id: z.string(),
  equipment_id: z.string(),
  status: z.string(),
  assigned_at: z.string(),
  released_at: z.string().nullable(),
  release_reason: z.string().nullable(),
})

// ─── User Management ────────────────────────────────────────────────────────

export const UserRoleSchema = z.enum([
  'admin',
  'doctor',
  'nurse',
  'operator',
])

export const UserSchema = z.object({
  id: z.number().int(),
  username: z.string(),
  email: z.string().email(),
  role: UserRoleSchema,
  is_active: z.boolean(),
})

export const UsersResponseSchema = z.array(UserSchema)

export const CreateUserRequestSchema = z.object({
  username: z.string().min(3).max(50),
  email: z.string().email(),
  password: z.string().min(8).max(72),
  role: UserRoleSchema,
})

export const UpdateUserRequestSchema = z.object({
  role: UserRoleSchema.optional(),
  is_active: z.boolean().optional(),
})

// Type exports
export type User = z.infer<typeof UserSchema>
export type UserRole = z.infer<typeof UserRoleSchema>
export type CreateUserRequest = z.infer<typeof CreateUserRequestSchema>
export type UpdateUserRequest = z.infer<typeof UpdateUserRequestSchema>

// ─── Lifecycle type exports ──────────────────────────────────────────────────
export type PatientIntakeRequest = z.infer<typeof PatientIntakeRequestSchema>
export type PatientIntakeResponse = z.infer<typeof PatientIntakeResponseSchema>
export type DischargeRequest = z.infer<typeof DischargeRequestSchema>
export type DischargeResponse = z.infer<typeof DischargeResponseSchema>
export type TransferRequest = z.infer<typeof TransferRequestSchema>
export type TransferResponse = z.infer<typeof TransferResponseSchema>
export type BedCleaningResponse = z.infer<typeof BedCleaningResponseSchema>
export type EquipmentAssignRequest = z.infer<typeof EquipmentAssignRequestSchema>
export type EquipmentReleaseRequest = z.infer<typeof EquipmentReleaseRequestSchema>
export type EquipmentAssignmentResponse = z.infer<typeof EquipmentAssignmentResponseSchema>
