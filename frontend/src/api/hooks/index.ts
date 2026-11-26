/**
 * hooks/index.ts — TanStack Query hooks for all backend endpoints.
 *
 * Rules:
 * - Never call fetch directly; use apiGet/apiPost from client.ts
 * - Validate every response with Zod; on failure show schema error
 * - staleTime ~15s; refetchInterval only on Command Centre + Queue hooks
 * - Retry 1 for GET, 0 for mutations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ZodError, ZodSchema } from 'zod'
import { apiGet, apiPost, apiPatch, ApiRequestError } from '../client'
import {
  PatientsResponseSchema,
  BedsResponseSchema,
  BedCreateRequestSchema,
  BedCreateResponseSchema,
  StaffResponseSchema,
  EquipmentResponseSchema,
  MetricsResponseSchema,
  AuditResponseSchema,
  RecommendResponseSchema,
  ApproveRequestSchema,
  ApproveResponseSchema,
  RejectRequestSchema,
  RejectResponseSchema,
  SurgeResponseSchema,
  Patient,
  Bed,
  BedCreateRequest,
  Staff,
  Equipment,
  Metrics,
  AuditEntry,
  RecommendResponse,
  ApproveArgs,
  ApproveResponse,
  RejectArgs,
  RejectResponse,
  SurgeResponse,
  UsersResponseSchema,
  UserSchema,
  User,
  CreateUserRequest,
  UpdateUserRequest,
  RecommendationAlgorithm,
  PatientIntakeRequestSchema,
  PatientIntakeResponseSchema,
  DischargeRequestSchema,
  DischargeResponseSchema,
  TransferRequestSchema,
  TransferResponseSchema,
  BedCleaningResponseSchema,
  EquipmentAssignRequestSchema,
  EquipmentReleaseRequestSchema,
  EquipmentAssignmentResponseSchema,
  PatientIntakeRequest,
  PatientIntakeResponse,
  DischargeRequest,
  DischargeResponse,
  TransferRequest,
  TransferResponse,
  BedCleaningResponse,
  EquipmentAssignRequest,
  EquipmentReleaseRequest,
  EquipmentAssignmentResponse,
} from '../schemas'

// ─── Validation helper ────────────────────────────────────────────────────────

function validate<T>(schema: ZodSchema<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) {
    console.error('[CareGrid] Schema validation failed:', result.error.format())
    throw new Error(`Unexpected response from server: ${result.error.issues[0]?.message ?? 'schema mismatch'}`)
  }
  return result.data
}

// ─── Error normalizer ─────────────────────────────────────────────────────────

export function getErrorMessage(err: unknown): string {
  if (err instanceof ApiRequestError) return err.message
  if (err instanceof ZodError) return `Unexpected response from server`
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const QUERY_KEYS = {
  patients: ['patients'] as const,
  beds: ['beds'] as const,
  staff: ['staff'] as const,
  equipment: ['equipment'] as const,
  metrics: ['metrics'] as const,
  audit: ['audit'] as const,
  users: ['users'] as const,
}


// ─── User Management ────────────────────────────────────────────────────────

// GET /auth/users
export function useUsers() {
  return useQuery<User[], Error>({
    queryKey: QUERY_KEYS.users,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/auth/users')
      return validate(UsersResponseSchema, raw)
    },
    staleTime: 15_000,
    retry: 1,
  })
}

// POST /auth/users
export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation<User, Error, CreateUserRequest>({
    mutationFn: async (userData) => {
      const raw = await apiPost<unknown>('/auth/users', userData)
      return validate(UserSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.users,
      })
    },
    retry: 0,
  })
}

// PATCH /auth/users/{user_id}
export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation<
    User,
    Error,
    { userId: number; updates: UpdateUserRequest }
  >({
    mutationFn: async ({ userId, updates }) => {
      const raw = await apiPatch<unknown>(
        `/auth/users/${userId}`,
        updates,
      )
      return validate(UserSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.users,
      })
    },
    retry: 0,
  })
}

// ─── GET /patients ────────────────────────────────────────────────────────────

export function usePatients(refetchInterval?: number) {
  return useQuery<Patient[], Error>({
    queryKey: QUERY_KEYS.patients,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/patients')
      const { patients } = validate(PatientsResponseSchema, raw)
      return patients
    },
    staleTime: 15_000,
    retry: 1,
    refetchInterval,
  })
}

// ─── GET /beds ────────────────────────────────────────────────────────────────

export function useBeds(refetchInterval?: number) {
  return useQuery<Bed[], Error>({
    queryKey: QUERY_KEYS.beds,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/beds')
      const { beds } = validate(BedsResponseSchema, raw)
      return beds
    },
    staleTime: 15_000,
    retry: 1,
    refetchInterval,
  })
}

// ─── GET /staff ───────────────────────────────────────────────────────────────

export function useStaff() {
  return useQuery<Staff[], Error>({
    queryKey: QUERY_KEYS.staff,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/staff')
      const { staff } = validate(StaffResponseSchema, raw)
      return staff
    },
    staleTime: 15_000,
    retry: 1,
  })
}

// ─── GET /equipment ───────────────────────────────────────────────────────────

export function useEquipment() {
  return useQuery<Equipment[], Error>({
    queryKey: QUERY_KEYS.equipment,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/equipment')
      const { equipment } = validate(EquipmentResponseSchema, raw)
      return equipment
    },
    staleTime: 15_000,
    retry: 1,
  })
}

// ─── GET /metrics ─────────────────────────────────────────────────────────────

export function useMetrics(
  refetchInterval?: number,
  enabled: boolean = true
) {
  return useQuery<Metrics, Error>({
    queryKey: QUERY_KEYS.metrics,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/metrics')
      return validate(MetricsResponseSchema, raw)
    },
    staleTime: 15_000,
    retry: 1,
    refetchInterval,
    enabled,
  })
}

// ─── GET /audit ───────────────────────────────────────────────────────────────

export function useAudit() {
  return useQuery<AuditEntry[], Error>({
    queryKey: QUERY_KEYS.audit,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/audit')
      const { audit } = validate(AuditResponseSchema, raw)
      return audit
    },
    staleTime: 15_000,
    retry: 1,
  })
}

export const useAuditLog = useAudit

// ─── POST /allocation/recommend ───────────────────────────────────────────────

export interface RecommendArgs {
  patient_id: string
  algorithm?: RecommendationAlgorithm
}

export type RecommendInput = RecommendArgs | string

function useRecommendationMutation() {
  return useMutation<RecommendResponse, Error, RecommendInput>({
    mutationFn: async (arg: RecommendInput) => {
      const patient_id = typeof arg === 'string' ? arg : arg.patient_id
      const algorithm = typeof arg === 'string' ? 'rule_based' : arg.algorithm ?? 'rule_based'
      const raw = await apiPost<unknown>('/allocation/recommend', {
        patient_id,
        algorithm,
      })
      return validate(RecommendResponseSchema, raw)
    },
    retry: 0,
  })
}

export function useRecommend() {
  return useRecommendationMutation()
}

export function useRecommendAllocation() {
  return useRecommendationMutation()
}

// ─── POST /allocation/approve ─────────────────────────────────────────────────

export function useApprove() {
  const queryClient = useQueryClient()
  return useMutation<ApproveResponse, Error, ApproveArgs>({
    mutationFn: async (args: ApproveArgs) => {
      const request = validate(ApproveRequestSchema, args)
      const raw = await apiPost<unknown>('/allocation/approve', request)
      return validate(ApproveResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.beds })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.patients })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.equipment })
    },
    retry: 0,
  })
}

export function useApproveAllocation() {
  const queryClient = useQueryClient()
  return useMutation<ApproveResponse, Error, ApproveArgs>({
    mutationFn: async (args: ApproveArgs) => {
      const request = validate(ApproveRequestSchema, args)
      const raw = await apiPost<unknown>('/allocation/approve', request)
      return validate(ApproveResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.beds })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.patients })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.equipment })
    },
    retry: 0,
  })
}

// ─── POST /surge/simulate ─────────────────────────────────────────────────────

export function useRejectAllocation() {
  const queryClient = useQueryClient()
  return useMutation<RejectResponse, Error, RejectArgs>({
    mutationFn: async (args: RejectArgs) => {
      const request = validate(RejectRequestSchema, args)
      const raw = await apiPost<unknown>('/allocation/reject', request)
      return validate(RejectResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

export interface SurgeArgs {
  adaptive?: boolean
  arrival_rate_multiplier: number
  duration_hours: number
}

export function useSurgeSimulate() {
  return useMutation<SurgeResponse, Error, SurgeArgs>({
    mutationFn: async (args: SurgeArgs) => {
      const raw = await apiPost<unknown>('/surge/simulate', args)
      return validate(SurgeResponseSchema, raw)
    },
    retry: 0,
  })
}

export const useSimulateSurge = useSurgeSimulate

// ─── Patient Lifecycle & Resource Mutations ─────────────────────────────────

// POST /patients/intake
export function useIntakePatient() {
  const queryClient = useQueryClient()
  return useMutation<PatientIntakeResponse, Error, PatientIntakeRequest>({
    mutationFn: async (args) => {
      const request = validate(PatientIntakeRequestSchema, args)
      const raw = await apiPost<unknown>('/patients/intake', request)
      return validate(PatientIntakeResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.patients })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

// POST /patients/{patient_id}/discharge
export function useDischargePatient() {
  const queryClient = useQueryClient()
  return useMutation<
    DischargeResponse,
    Error,
    { patient_id: string } & Partial<DischargeRequest>
  >({
    mutationFn: async ({ patient_id, ...body }) => {
      const request = validate(DischargeRequestSchema, body)
      const raw = await apiPost<unknown>(
        `/patients/${encodeURIComponent(patient_id)}/discharge`,
        request
      )
      return validate(DischargeResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.patients })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.beds })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.equipment })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

// POST /patients/{patient_id}/transfer
export function useTransferPatient() {
  const queryClient = useQueryClient()
  return useMutation<
    TransferResponse,
    Error,
    { patient_id: string } & TransferRequest
  >({
    mutationFn: async ({ patient_id, ...body }) => {
      const request = validate(TransferRequestSchema, body)
      const raw = await apiPost<unknown>(
        `/patients/${encodeURIComponent(patient_id)}/transfer`,
        request
      )
      return validate(TransferResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.patients })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.beds })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

// POST /beds
export function useCreateBed() {
  const queryClient = useQueryClient()
  return useMutation<Bed, Error, BedCreateRequest>({
    mutationFn: async (body) => {
      const request = validate(BedCreateRequestSchema, body)
      const raw = await apiPost<unknown>('/beds', request)
      return validate(BedCreateResponseSchema, raw).bed
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.beds })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

// POST /beds/{bed_id}/cleaning-complete
export function useCompleteBedCleaning() {
  const queryClient = useQueryClient()
  return useMutation<BedCleaningResponse, Error, string>({
    mutationFn: async (bed_id) => {
      const raw = await apiPost<unknown>(
        `/beds/${encodeURIComponent(bed_id)}/cleaning-complete`,
        {}
      )
      return validate(BedCleaningResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.beds })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

// POST /equipment/{equipment_id}/assign
export function useAssignEquipment() {
  const queryClient = useQueryClient()
  return useMutation<
    EquipmentAssignmentResponse,
    Error,
    { equipment_id: string } & EquipmentAssignRequest
  >({
    mutationFn: async ({ equipment_id, ...body }) => {
      const request = validate(EquipmentAssignRequestSchema, body)
      const raw = await apiPost<unknown>(
        `/equipment/${encodeURIComponent(equipment_id)}/assign`,
        request
      )
      return validate(EquipmentAssignmentResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.equipment })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

// POST /equipment/{equipment_id}/release
export function useReleaseEquipment() {
  const queryClient = useQueryClient()
  return useMutation<
    EquipmentAssignmentResponse,
    Error,
    { equipment_id: string } & Partial<EquipmentReleaseRequest>
  >({
    mutationFn: async ({ equipment_id, ...body }) => {
      const request = validate(EquipmentReleaseRequestSchema, body)
      const raw = await apiPost<unknown>(
        `/equipment/${encodeURIComponent(equipment_id)}/release`,
        request
      )
      return validate(EquipmentAssignmentResponseSchema, raw)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.equipment })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.metrics })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.audit })
    },
    retry: 0,
  })
}

