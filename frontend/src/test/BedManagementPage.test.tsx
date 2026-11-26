import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthContext } from '@/auth/AuthContext';
import type { UserRole } from '@/auth/types';
import type { Bed, BedCreateRequest } from '@/api/schemas';
import { ToastProvider } from '@/components/feedback/Toast';
import { BedManagementPage } from '@/pages/BedManagementPage';

function renderBeds(role: UserRole, beds: Bed[] = [
    { bed_id: 'ICU-01', bed_type: 'ICU', ward: 'ICU-A', status: 'CLEANING', isolation_capable: false },
]) {
  const createBed = vi.fn((request: BedCreateRequest) => {
    if (beds.some((bed) => bed.bed_id === request.bed_id)) {
      return Response.json({ detail: 'Bed ID already exists' }, { status: 409 });
    }
    const bed = { ...request, status: 'AVAILABLE' };
    beds.push(bed);
    return Response.json({ message: 'Bed created successfully', bed }, { status: 201 });
  });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/beds')) {
      return init.method === 'POST'
        ? createBed(JSON.parse(String(init.body)))
        : Response.json({ beds });
    }
    if (url.endsWith('/beds/ICU-01/cleaning-complete') && init.method === 'POST') {
      beds[0]!.status = 'AVAILABLE';
      return Response.json({ bed_id: 'ICU-01', status: 'AVAILABLE' });
    }
    throw new Error('Unexpected request to ' + url);
  }));

  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthContext.Provider value={{
        user: { id: 1, username: role, email: 'staff@example.com', role, is_active: true },
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
      }}>
        <ToastProvider>
          <BedManagementPage />
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );

  return createBed;
}

describe('Bed Management', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows the assigned patient on the occupied bed tile and in its details', async () => {
    renderBeds('nurse', [
      { bed_id: 'ICU-01', bed_type: 'ICU', ward: 'ICU-A', status: 'OCCUPIED', isolation_capable: false, patient_id: 'PAT-101', predicted_los: 1.3 },
      { bed_id: 'ICU-02', bed_type: 'ICU', ward: 'ICU-A', status: 'OCCUPIED', isolation_capable: false, patient_id: null },
      { bed_id: 'ICU-03', bed_type: 'ICU', ward: 'ICU-A', status: 'CLEANING', isolation_capable: false, patient_id: 'PAT-103' },
      { bed_id: 'ICU-04', bed_type: 'ICU', ward: 'ICU-A', status: 'OCCUPIED', isolation_capable: false },
    ]);

    const tile = await screen.findByRole('button', { name: /Bed ICU-01, OCCUPIED.*Patient ID PAT-101/ });
    expect(within(tile).getByText('PAT-101')).toBeTruthy();
    const unlinkedBed = screen.getByRole('button', { name: /Bed ICU-02, OCCUPIED.*No assignment recorded/ });
    expect(within(unlinkedBed).getByText('No assignment recorded')).toBeTruthy();
    const missingFieldBed = screen.getByRole('button', { name: /Bed ICU-04, OCCUPIED.*Patient ID unavailable/ });
    expect(within(missingFieldBed).getByText('Patient ID unavailable')).toBeTruthy();
    expect(screen.queryByText('PAT-103')).toBeNull();

    fireEvent.click(tile);
    const dialog = within(screen.getByRole('dialog', { name: /Bed Details.*ICU-01/ }));
    expect(dialog.getByText('Patient ID')).toBeTruthy();
    expect(dialog.getByText('PAT-101')).toBeTruthy();
    expect(dialog.getByText('Predicted LOS')).toBeTruthy();
    expect(dialog.getByText('1.3d')).toBeTruthy();

    fireEvent.click(dialog.getByRole('button', { name: 'Close' }));
    fireEvent.click(unlinkedBed);
    const unlinkedDetails = within(screen.getByRole('dialog', { name: /Bed Details.*ICU-02/ }));
    expect(unlinkedDetails.getByText('Patient ID')).toBeTruthy();
    expect(unlinkedDetails.getByText('No assignment recorded')).toBeTruthy();
  });

  it('keeps a duplicate submission editable and refreshes inventory after a successful retry', async () => {
    const createBed = renderBeds('admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Add Bed' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Add Bed' }));
    const id = dialog.getByLabelText('Bed ID');
    const submit = dialog.getByRole('button', { name: 'Add Bed' });

    fireEvent.change(id, { target: { value: 'ICU-01' } });
    fireEvent.change(dialog.getByLabelText('Bed Type'), { target: { value: 'ICU' } });
    fireEvent.change(dialog.getByLabelText('Ward'), { target: { value: ' constructor ' } });
    fireEvent.click(dialog.getByLabelText('Isolation capable'));
    fireEvent.click(submit);
    expect((await dialog.findByRole('alert')).textContent).toBe('Bed ID already exists');

    fireEvent.change(id, { target: { value: ' ICU-02 ' } });
    fireEvent.click(submit);
    expect(await screen.findByRole('button', { name: /Bed ICU-02, AVAILABLE/ })).toBeTruthy();
    expect(createBed).toHaveBeenLastCalledWith({
      bed_id: 'ICU-02', bed_type: 'ICU', ward: 'constructor', isolation_capable: true,
    });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('keeps the cleaning workflow available to nurses', async () => {
    const createBed = renderBeds('nurse');
    fireEvent.click(await screen.findByRole('button', { name: /Bed ICU-01, CLEANING/ }));
    expect(screen.queryByRole('button', { name: 'Add Bed' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Complete Cleaning' }));
    expect(await screen.findByRole('button', { name: /Bed ICU-01, AVAILABLE/ })).toBeTruthy();
    expect(createBed).not.toHaveBeenCalled();
  });
});
