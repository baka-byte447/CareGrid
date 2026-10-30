import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { usePatients, useBeds, useMetrics } from '@/api/hooks';
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
});
