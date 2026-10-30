import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiGet, apiPost, ApiRequestError } from '@/api/client';

describe('HTTP API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('performs successful GET request and returns JSON', async () => {
    const fakeData = { status: 'ok', value: 42 };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => fakeData,
    } as unknown as Response);

    const result = await apiGet('/metrics');
    expect(result).toEqual(fakeData);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/metrics',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('performs successful POST request with body', async () => {
    const fakeResponse = { status: 'APPROVED' };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => fakeResponse,
    } as unknown as Response);

    const payload = { patient_id: 'PAT-01', bed_id: 'ICU-01' };
    const result = await apiPost('/allocation/approve', payload);
    expect(result).toEqual(fakeResponse);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/allocation/approve',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('throws ApiRequestError with 409 Conflict message when bed is occupied', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Bed ICU-01 is already occupied.' }),
    } as unknown as Response);

    await expect(
      apiPost('/allocation/approve', { patient_id: 'P1', bed_id: 'B1' })
    ).rejects.toThrow(ApiRequestError);
  });

  it('throws ApiRequestError with 404 Not Found when patient or bed does not exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Patient PAT-999 not found.' }),
    } as unknown as Response);

    await expect(apiGet('/patients/PAT-999')).rejects.toThrow(ApiRequestError);
  });

  it('throws ApiRequestError on 500 server error', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal allocation solver error.' }),
    } as unknown as Response);

    await expect(apiGet('/metrics')).rejects.toThrow(ApiRequestError);
  });

  it('handles network failure (fetch throws TypeError)', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(apiGet('/metrics')).rejects.toThrow(ApiRequestError);
  });
});
