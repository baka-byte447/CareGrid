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
import { apiGet, apiPost, ApiRequestError } from '../client'
import {
  PatientsResponseSchema,
  BedsResponseSchema,
  StaffResponseSchema,
  EquipmentResponseSchema,
  MetricsResponseSchema,
  AuditResponseSchema,
  RecommendResponseSchema,
  ApproveResponseSchema,
  SurgeResponseSchema,
  Patient,
  Bed,
  Staff,
  Equipment,
  Metrics,
  AuditEntry,
  RecommendResponse,
  ApproveResponse,
  SurgeResponse,
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

export function useMetrics(refetchInterval?: number) {
  return useQuery<Metrics, Error>({
    queryKey: QUERY_KEYS.metrics,
    queryFn: async () => {
      const raw = await apiGet<unknown>('/metrics')
      return validate(MetricsResponseSchema, raw)
    },
    staleTime: 15_000,
    retry: 1,
    refetchInterval,
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

export function useRecommend() {
  return useMutation<RecommendResponse, Error, string>({
    mutationFn: async (patientId: string) => {
      const raw = await apiPost<unknown>('/allocation/recommend', { patient_id: patientId })
      return validate(RecommendResponseSchema, raw)
    },
    retry: 0,
  })
}

export function useRecommendAllocation() {
  return useMutation<RecommendResponse, Error, { patient_id: string } | string>({
    mutationFn: async (arg: { patient_id: string } | string) => {
      const patientId = typeof arg === 'string' ? arg : arg.patient_id
      const raw = await apiPost<unknown>('/allocation/recommend', { patient_id: patientId })
      return validate(RecommendResponseSchema, raw)
    },
    retry: 0,
  })
}

// ─── POST /allocation/approve ─────────────────────────────────────────────────

export interface ApproveArgs {
  patientId?: string
  bedId?: string
  patient_id?: string
  bed_id?: string
}

export function useApprove() {
  const queryClient = useQueryClient()
  return useMutation<ApproveResponse, Error, { patientId: string; bedId: string }>({
    mutationFn: async ({ patientId, bedId }: { patientId: string; bedId: string }) => {
      const raw = await apiPost<unknown>('/allocation/approve', {
        patient_id: patientId,
        bed_id: bedId,
      })
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
      const patient_id = args.patient_id ?? args.patientId ?? ''
      const bed_id = args.bed_id ?? args.bedId ?? ''
      const raw = await apiPost<unknown>('/allocation/approve', {
        patient_id,
        bed_id,
      })
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

export interface SurgeArgs {
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

