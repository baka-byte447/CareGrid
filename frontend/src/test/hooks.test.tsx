import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { usePatients, useBeds, useMetrics, useRecommend, useRecommendAllocation } from '@/api/hooks';
import { mockPatients } from './fixtures/patients.fixture';
import { mockBeds } from './fixtures/beds.fixture';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('TanStack Query Hooks Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('usePatients fetches and validates patient list', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ patients: mockPatients }),
    } as unknown as Response);

    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(3);
    expect(result.current.data?.[0]?.patient_id).toBe('PAT-001');
  });

  it('useBeds fetches and validates beds list', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ beds: mockBeds }),
    } as unknown as Response);

    const { result } = renderHook(() => useBeds(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(4);
    expect(result.current.data?.[0]?.bed_id).toBe('ICU-01');
  });

  it('useMetrics fetches and parses hospital capacity metrics', async () => {
    const fakeMetrics = {
      patients_total: 100,
      patients_waiting: 20,
      patients_admitted: 80,
      beds_total: 80,
      beds_available: 10,
      beds_occupied: 70,
      bed_occupancy_rate: 0.875,
      ventilators_total: 15,
      ventilators_available: 5,
      ventilators_in_use: 10,
      approved_allocations: 30,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => fakeMetrics,
    } as unknown as Response);

    const { result } = renderHook(() => useMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.bed_occupancy_rate).toBeCloseTo(0.875);
    expect(result.current.data?.beds_available).toBe(10);
  });

  it('useRecommendAllocation sends the selected DQN algorithm', async () => {
    const dqnResponse = {
      recommendation_id: 801,
      patient_id: 'PAT-001',
      recommended_bed_id: 'ICU-01',
      algorithm: 'dqn_safe',
      reason: '',
      status: 'RECOMMENDED',
      safety: {
        overridden: false,
        rule_triggered: null,
        original_action: 0,
        reason: null,
      },
      q_values: [0.8, 0.4, 0.2, -0.1],
      los_estimate_days: 4.25,
      proposed_action: 0,
      final_action: 0,
      proposed_bed_type: 'ICU',
      final_bed_type: 'ICU',
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => dqnResponse,
    } as unknown as Response);
    globalThis.fetch = fetchMock;

    const { result } = renderHook(() => useRecommendAllocation(), {
      wrapper: createWrapper(),
    });
    result.current.mutate({ patient_id: 'PAT-001', algorithm: 'dqn_safe' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const request = fetchMock.mock.calls[0];
    expect(request?.[0]).toBe('/api/allocation/recommend');
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      patient_id: 'PAT-001',
      algorithm: 'dqn_safe',
    });
    expect(result.current.data?.safety?.overridden).toBe(false);
  });

  it('keeps the legacy useRecommend string call and defaults it to Rule-Based', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        recommendation_id: 802,
        patient_id: 'PAT-001',
        recommended_bed_id: 'ICU-01',
        algorithm: 'rule_based',
        reason: 'Compatible ICU bed available',
        status: 'RECOMMENDED',
      }),
    } as unknown as Response);
    globalThis.fetch = fetchMock;

    const { result } = renderHook(() => useRecommend(), {
      wrapper: createWrapper(),
    });
    result.current.mutate('PAT-001');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      patient_id: 'PAT-001',
      algorithm: 'rule_based',
    });
  });
});
