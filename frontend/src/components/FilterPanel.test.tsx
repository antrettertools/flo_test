import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { useExplorerStore } from '../state/explorerStore';
import { FilterPanel } from './FilterPanel';

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

describe('FilterPanel', () => {
  it('shows the size-class filter on the generation tab', () => {
    renderWithQuery(<FilterPanel />);
    expect(screen.getByLabelText(/size class/i)).toBeInTheDocument();
  });

  it('hides the size-class filter on the storage tab (all values are unknown)', () => {
    useExplorerStore.setState((s) => ({ ...s, tab: 'storage' }));
    renderWithQuery(<FilterPanel />);
    expect(screen.queryByLabelText(/size class/i)).not.toBeInTheDocument();
  });

  it('renders metric and time-mode toggles', () => {
    renderWithQuery(<FilterPanel />);
    expect(screen.getByText(/count/i)).toBeInTheDocument();
    expect(screen.getByText(/capacity/i)).toBeInTheDocument();
  });
});
