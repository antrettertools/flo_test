import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => {
  class MapMock {
    on = vi.fn();
    addSource = vi.fn();
    addLayer = vi.fn();
    setFeatureState = vi.fn();
    remove = vi.fn();
    fitBounds = vi.fn();
    getSource = vi.fn();
  }
  return { Map: MapMock, default: { Map: MapMock } };
});

import { MapView } from './MapView';

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('MapView', () => {
  it('renders a map container without crashing', () => {
    renderWithQuery(<MapView />);
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
  });
});
