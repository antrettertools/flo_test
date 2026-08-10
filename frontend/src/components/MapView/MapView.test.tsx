import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { act } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { layerClickHandlers, addedSources } = vi.hoisted(() => ({
  layerClickHandlers: new Map<string, (e: unknown) => void>(),
  addedSources: new Set<string>(),
}));

vi.mock('maplibre-gl', () => {
  class MapMock {
    on = vi.fn((event: string, layerId: string, handler: (e: unknown) => void) => {
      if (event === 'click') layerClickHandlers.set(layerId, handler);
    });
    addSource = vi.fn((id: string) => {
      addedSources.add(id);
    });
    getSource = vi.fn((id: string) => (addedSources.has(id) ? {} : undefined));
    addLayer = vi.fn();
    setFeatureState = vi.fn();
    remove = vi.fn();
    fitBounds = vi.fn();
  }
  return { Map: MapMock, default: { Map: MapMock } };
});

vi.mock('../../api/client', () => ({
  apiGet: vi.fn((path: string) => {
    if (path.includes('/geojson')) {
      return Promise.resolve({ type: 'FeatureCollection', features: [] });
    }
    if (path.includes('/capacity/totals')) {
      return Promise.resolve({ as_of_date: '2026-08-10', include_decommissioned: false, group_by: ['region'], results: [] });
    }
    return Promise.resolve({});
  }),
}));

import { useExplorerStore } from '../../state/explorerStore';
import { MapView } from './MapView';

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('MapView', () => {
  beforeEach(() => {
    useExplorerStore.setState(useExplorerStore.getInitialState());
    layerClickHandlers.clear();
    addedSources.clear();
  });

  it('renders a map container without crashing', () => {
    renderWithQuery(<MapView />);
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
  });

  describe('Kreis click handler stale-closure regression', () => {
    it('reads the currently selected Land at click time, not the Land selected when the handler was first registered', async () => {
      // Select Land A first — this is the render during which the map's
      // 'kreis-fill' click handler gets registered (once, per the
      // `!map.getSource(sourceId)` guard in MapView.tsx).
      useExplorerStore.setState({ selection: { level: 'land', landAgs: 'A', kreisAgs: null } });

      renderWithQuery(<MapView />);

      await waitFor(() => {
        expect(layerClickHandlers.has('kreis-fill')).toBe(true);
      });

      // Simulate the user going back to national level and selecting a
      // *different* Land (B) — without unmounting MapView. Because
      // 'kreis-source' is already registered, MapView's effect guard skips
      // re-adding the source/layer/handler, so the original handler
      // instance (captured during Land A's render) is still the one that
      // will fire.
      act(() => {
        useExplorerStore.setState({ selection: { level: 'land', landAgs: 'B', kreisAgs: null } });
      });

      // The handler must not have been re-registered (this is what makes
      // the bug possible in the first place) — the same 'kreis-fill' entry
      // is still the one 'on' was called with, confirming we're exercising
      // the actual stale-closure path rather than a freshly-bound handler.
      const handlerAfterReselect = layerClickHandlers.get('kreis-fill');
      expect(handlerAfterReselect).toBeDefined();
      expect(addedSources.has('kreis-source')).toBe(true); // guard skipped re-adding

      // Fire a Kreis click as MapLibre would, with a feature carrying the
      // clicked region's ags. Asserting on the resulting store state (rather
      // than spying on `selectKreis`) avoids a stale-reference pitfall of
      // its own: MapView's closure holds the actual `selectKreis` function
      // captured from the hook at render time, so replacing the method on
      // a `getState()` snapshot afterward would not be the function the
      // closure calls.
      act(() => {
        handlerAfterReselect?.({ features: [{ properties: { ags: 'X' } }] });
      });

      // Must use B (the currently selected Land), not A (the Land that was
      // selected when the handler closure was created).
      expect(useExplorerStore.getState().selection).toEqual({ level: 'kreis', landAgs: 'B', kreisAgs: 'X' });
    });
  });
});
