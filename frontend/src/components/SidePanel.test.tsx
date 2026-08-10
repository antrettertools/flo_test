import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import { useExplorerStore } from '../state/explorerStore';
import { SidePanel } from './SidePanel';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('SidePanel', () => {
  it('renders the breadcrumb, filter controls, and chart', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      as_of_date: '2026-08-10',
      include_decommissioned: false,
      group_by: ['technology'],
      results: [],
    });
    renderWithQuery(<SidePanel />);
    expect(screen.getByText('Germany')).toBeInTheDocument();
    expect(await screen.findByTestId('technology-chart')).toBeInTheDocument();
  });

  it('requests period additions (not totals) when timeMode is period', async () => {
    const apiGetSpy = vi.spyOn(client, 'apiGet').mockResolvedValue({
      date_from: null,
      date_to: null,
      group_by: ['technology'],
      results: [],
    });
    useExplorerStore.setState((s) => ({ filters: { ...s.filters, timeMode: 'period' } }));
    renderWithQuery(<SidePanel />);
    await screen.findByTestId('technology-chart');
    expect(apiGetSpy).toHaveBeenCalledWith('/capacity/additions', expect.anything());
  });
});
