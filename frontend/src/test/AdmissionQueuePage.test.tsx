import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthContext } from '@/auth/AuthContext';
import { ToastProvider } from '@/components/feedback/Toast';
import { AdmissionQueuePage } from '@/pages/AdmissionQueuePage';

afterEach(() => vi.unstubAllGlobals());

it('registers a waiting patient without asking for or sending an LOS', async () => {
  const patients: object[] = [];
  const intake = vi.fn((body: object) => {
    const patient = {
      ...body,
      patient_id: 'P1011',
      current_status: 'WAITING',
      arrival_time: '2026-11-26T20:09:00Z',
      predicted_los: null,
    };
    patients.push(patient);
    return Response.json({ ...patient, encounter_id: 12, encounter_status: 'WAITING' }, { status: 201 });
  });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/patients')) return Response.json({ patients });
    if (url.endsWith('/beds')) return Response.json({ beds: [] });
    if (url.endsWith('/clinical/activity')) return Response.json({ telemetry: [], fhir_encounters: [] });
    if (url.endsWith('/patients/intake') && init.method === 'POST') {
      return intake(JSON.parse(String(init.body)));
    }
    throw new Error('Unexpected request to ' + url);
  }));
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <AuthContext.Provider value={{
          user: { id: 1, username: 'nurse', email: 'nurse@example.com', role: 'nurse', is_active: true },
          isAuthenticated: true,
          isLoading: false,
          login: vi.fn(),
          logout: vi.fn(),
        }}>
          <ToastProvider>
            <AdmissionQueuePage />
          </ToastProvider>
        </AuthContext.Provider>
      </QueryClientProvider>
    </MemoryRouter>,
  );

  fireEvent.click(await screen.findByRole('button', { name: 'New Patient' }));
  const dialog = within(screen.getByRole('dialog', { name: 'Register New Patient Intake' }));
  expect(dialog.queryByText(/predicted los/i)).toBeNull();
  fireEvent.click(dialog.getByRole('button', { name: 'Register Patient' }));

  const row = await screen.findByRole('row', { name: /P1011/ });
  expect(within(row).getByText('—')).toBeTruthy();
  expect(intake).toHaveBeenCalledTimes(1);
  expect(intake.mock.calls[0]![0]).not.toHaveProperty('predicted_los');
});
