import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuditLogPage } from '@/pages/AuditLogPage';

const ruleBasedAudit = {
  patient_id: 'PAT-RULE',
  bed_id: 'ICU-01',
  action: 'APPROVED',
  algorithm: 'rule_based',
  timestamp: '2026-11-24T10:00:00+00:00',
};

const dqnAudit = {
  patient_id: 'PAT-DQN',
  bed_id: 'ICU-02',
  action: 'APPROVED',
  algorithm: 'dqn_safe',
  timestamp: '2026-11-24T11:00:00+00:00',
};

function renderAudit(entries: typeof ruleBasedAudit[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ audit: entries }),
  } as unknown as Response);

  return render(
    <QueryClientProvider client={queryClient}>
      <AuditLogPage />
    </QueryClientProvider>,
  );
}

describe('AuditLogPage algorithm filter', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('offers only algorithms present in actual audit records', async () => {
    renderAudit([ruleBasedAudit]);

    await screen.findByText('PAT-RULE');
    const algorithmFilter = screen.getAllByRole('combobox')[1] as HTMLSelectElement;
    expect(Array.from(algorithmFilter.options).map((option) => option.value)).toEqual([
      'ALL', 'rule_based',
    ]);
    expect(screen.queryByRole('option', { name: /DQN Safe/ })).toBeNull();
    expect(screen.getByText('Rule-Based', { exact: true })).toBeTruthy();
  });

  it('labels DQN Safe records and filters by the actual dqn_safe value', async () => {
    renderAudit([ruleBasedAudit, dqnAudit]);

    await screen.findByText('PAT-RULE');
    await screen.findByText('PAT-DQN');
    const algorithmFilter = screen.getAllByRole('combobox')[1] as HTMLSelectElement;
    expect(Array.from(algorithmFilter.options).map((option) => option.value)).toEqual([
      'ALL', 'dqn_safe', 'rule_based',
    ]);
    expect(screen.getByText('DQN Safe', { exact: true })).toBeTruthy();

    fireEvent.change(algorithmFilter, { target: { value: 'dqn_safe' } });

    await waitFor(() => {
      expect(screen.getByText('PAT-DQN')).toBeTruthy();
      expect(screen.queryByText('PAT-RULE')).toBeNull();
    });
  });
});
