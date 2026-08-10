import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => {
  class MapMock {
    on = vi.fn();
    addSource = vi.fn();
    addLayer = vi.fn();
    getLayer = vi.fn();
    removeLayer = vi.fn();
    removeSource = vi.fn();
    setFeatureState = vi.fn();
    remove = vi.fn();
    fitBounds = vi.fn();
    getSource = vi.fn();
    getZoom = vi.fn().mockReturnValue(5);
    getBounds = vi.fn().mockReturnValue({ toArray: () => [[0, 0], [1, 1]] });
  }
  return { Map: MapMock, default: { Map: MapMock } };
});

import App from './App';

function renderWithQuery() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

describe('App', () => {
  it('renders the Generation/Storage tabs and defaults to Generation', () => {
    renderWithQuery();
    expect(screen.getByRole('tab', { name: /generation/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /storage/i })).toHaveAttribute('aria-selected', 'false');
  });

  it('switches to the Storage tab on click', async () => {
    renderWithQuery();
    await userEvent.click(screen.getByRole('tab', { name: /storage/i }));
    expect(screen.getByRole('tab', { name: /storage/i })).toHaveAttribute('aria-selected', 'true');
  });
});
