import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import { DataProvenanceFooter } from './DataProvenanceFooter';

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('DataProvenanceFooter', () => {
  it('shows the last import date and region match rate', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      has_data: true,
      last_import_finished_at: '2026-08-10T16:46:34',
      vg250_source_version: 'vg250_01-01',
      region_join_match_rate: 0.9997819834,
      mastr_row_counts: {},
      capacity_rollup_row_count: 42,
    });
    renderWithQuery(<DataProvenanceFooter />);
    expect(await screen.findByText(/2026-08-10/)).toBeInTheDocument();
    expect(screen.getByText(/99\.98%/)).toBeInTheDocument();
  });

  it('shows a warning alert when has_data is false', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      has_data: false,
      last_import_finished_at: null,
      vg250_source_version: null,
      region_join_match_rate: null,
      mastr_row_counts: null,
      capacity_rollup_row_count: 0,
    });
    renderWithQuery(<DataProvenanceFooter />);
    expect(await screen.findByText(/no data/i)).toBeInTheDocument();
  });

  it('shows a rollup-missing warning when capacity_rollup is empty but data has been imported', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      has_data: true,
      last_import_finished_at: '2026-08-10T16:46:34',
      vg250_source_version: 'vg250_01-01',
      region_join_match_rate: 0.9997819834,
      mastr_row_counts: {},
      capacity_rollup_row_count: 0,
    });
    renderWithQuery(<DataProvenanceFooter />);
    expect(await screen.findByText(/rollup data missing/i)).toBeInTheDocument();
    // The normal "data as of" pill should still render alongside the warning.
    expect(screen.getByText(/2026-08-10/)).toBeInTheDocument();
  });

  it('does not show the rollup warning when capacity_rollup has rows', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      has_data: true,
      last_import_finished_at: '2026-08-10T16:46:34',
      vg250_source_version: 'vg250_01-01',
      region_join_match_rate: 0.9997819834,
      mastr_row_counts: {},
      capacity_rollup_row_count: 42,
    });
    renderWithQuery(<DataProvenanceFooter />);
    await screen.findByText(/2026-08-10/);
    expect(screen.queryByText(/rollup data missing/i)).not.toBeInTheDocument();
  });
});
