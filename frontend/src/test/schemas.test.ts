import { describe, it, expect } from 'vitest';
import {
  PatientSchema,
  PatientsResponseSchema,
  BedSchema,
  BedsResponseSchema,
  StaffSchema,
  EquipmentSchema,
  MetricsResponseSchema,
  AuditResponseSchema,
  RecommendResponseSchema,
  ApproveResponseSchema,
  SurgeResponseSchema,
} from '@/api/schemas';
import { mockPatients } from './fixtures/patients.fixture';
import { mockBeds } from './fixtures/beds.fixture';

describe('Zod API Response Schemas', () => {
  it('validates a valid patient record', () => {
    const valid = mockPatients[0];
    const parsed = PatientSchema.parse(valid);
    expect(parsed.patient_id).toBe('PAT-001');
    expect(parsed.acuity).toBe(5);
  });

  it('rejects invalid patient acuity (< 1 or > 5)', () => {
    const invalid = { ...mockPatients[0], acuity: 6 };
    expect(() => PatientSchema.parse(invalid)).toThrow();
  });

  it('validates patients response list', () => {
    const parsed = PatientsResponseSchema.parse({ patients: mockPatients });
    expect(parsed.patients).toHaveLength(3);
  });

  it('validates bed schema and bed types', () => {
    const valid = mockBeds[0];
    const parsed = BedSchema.parse(valid);
    expect(parsed.bed_type).toBe('ICU');
  });

  it('rejects unknown bed type', () => {
    const invalid = { ...mockBeds[0], bed_type: 'INVALID_WARD_TYPE' };
    expect(() => BedSchema.parse(invalid)).toThrow();
  });

  it('validates beds response list', () => {
    const parsed = BedsResponseSchema.parse({ beds: mockBeds });
    expect(parsed.beds).toHaveLength(4);
  });

  it('validates staff schema', () => {
    const valid = {
      staff_id: 'STF-01',
      role: 'Critical-care',
      skill_level: 'SENIOR',
      shift: 'Day',
      workload: 65,
    };
    const parsed = StaffSchema.parse(valid);
    expect(parsed.workload).toBe(65);
  });

  it('validates equipment schema', () => {
    const valid = {
      equipment_id: 'VENT-01',
      type: 'VENTILATOR',
      status: 'AVAILABLE',
      location: 'ICU-A',
    };
    const parsed = EquipmentSchema.parse(valid);
    expect(parsed.equipment_id).toBe('VENT-01');
  });

  it('validates live metrics response schema', () => {
    const valid = {
      patients_total: 100,
      patients_waiting: 25,
      patients_admitted: 75,
      beds_total: 80,
      beds_available: 15,
      beds_occupied: 65,
      bed_occupancy_rate: 0.8125,
      ventilators_total: 20,
      ventilators_available: 8,
      ventilators_in_use: 12,
      approved_allocations: 42,
    };
    const parsed = MetricsResponseSchema.parse(valid);
    expect(parsed.bed_occupancy_rate).toBeCloseTo(0.8125);
  });

  it('validates audit log response schema', () => {
    const valid = {
      audit: [
        {
          patient_id: 'PAT-001',
          bed_id: 'ICU-01',
          action: 'BED_ALLOCATED',
          algorithm: 'PPO_Policy',
          timestamp: '2026-10-30T17:15:00Z',
        },
      ],
    };
    const parsed = AuditResponseSchema.parse(valid);
    expect(parsed.audit).toHaveLength(1);
    expect(parsed.audit[0]?.action).toBe('BED_ALLOCATED');
  });

  it('validates recommendation response schema (recommended)', () => {
    const valid = {
      patient_id: 'PAT-001',
      recommended_bed_id: 'ICU-01',
      algorithm: 'PPO_Policy',
      reason: 'Optimal ICU match based on high acuity and ventilator requirement',
      status: 'RECOMMENDED',
    };
    const parsed = RecommendResponseSchema.parse(valid);
    expect(parsed.recommended_bed_id).toBe('ICU-01');
  });

  it('validates recommendation response schema (no suitable bed)', () => {
    const valid = {
      patient_id: 'PAT-001',
      recommended_bed_id: null,
      algorithm: 'PPO_Policy',
      reason: 'No isolation-capable beds currently available',
      status: 'NO_SUITABLE_BED',
    };
    const parsed = RecommendResponseSchema.parse(valid);
    expect(parsed.recommended_bed_id).toBeNull();
    expect(parsed.status).toBe('NO_SUITABLE_BED');
  });

  it('validates allocation approval response schema', () => {
    const valid = {
      patient_id: 'PAT-001',
      bed_id: 'ICU-01',
      status: 'APPROVED',
    };
    const parsed = ApproveResponseSchema.parse(valid);
    expect(parsed.status).toBe('APPROVED');
  });

  it('validates surge response schema with nested metrics', () => {
    const valid = {
      status: 'COMPLETED',
      arrival_rate_multiplier: 1.6,
      duration_hours: 24,
      patients_arrived: 45,
      simulation_start: '2026-03-14T00:00:00',
      simulation_end: '2026-03-15T00:00:00',
      metrics: {
        patients_total: 45,
        patients_admitted: 40,
        patients_discharged: 10,
        patients_still_waiting: 5,
        avg_wait_min: 32.5,
        median_wait_min: 25.0,
        avg_wait_incl_unadmitted_min: 35.0,
        p90_wait_incl_unadmitted_min: 65.0,
        p90_wait_min: 60.0,
        max_wait_min: 120.0,
        avg_wait_by_acuity_min: { '1': 10, '5': 45 },
        pct_admitted_within_60min: 0.88,
        icu_utilization: 0.95,
        step_down_utilization: 0.80,
        ward_utilization: 0.75,
        overall_bed_utilization: 0.82,
        ventilator_utilization: 0.70,
        bed_turnover_per_bed_per_day: 1.2,
        peak_waiting_queue: 8,
        constraint_violations: 0,
        measurement_window_hours: 24,
        waiting_patients_elapsed_wait_min: { avg: 15.0, max: 40.0 },
      },
    };
    const parsed = SurgeResponseSchema.parse(valid);
    expect(parsed.status).toBe('COMPLETED');
    expect(parsed.metrics.pct_admitted_within_60min).toBe(0.88);
  });
});
