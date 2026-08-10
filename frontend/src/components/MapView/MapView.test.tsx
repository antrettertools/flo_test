import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { act } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { layerClickHandlers, addedSources, addedLayers } = vi.hoisted(() => ({
  layerClickHandlers: new Map<string, (e: unknown) => void>(),
  addedSources: new Set<string>(),
  addedLayers: new Set<string>(),
}));

vi.mock('maplibre-gl', () => {
  class MapMock {
    on = vi.fn((event: string, layerId: string, handler: (e: unknown) => void) => {
      if (event === 'click') layerClickHandlers.set(layerId, handler);
    });
    addSource = vi.fn((id: string) => {
      addedSources.add(id);
    });
    getSource = vi.fn((id: string) => (addedSources.has(id) ? { setData: vi.fn() } : undefined));
    removeSource = vi.fn((id: string) => {
      addedSources.delete(id);
    });
    addLayer = vi.fn((layer: { id: string }) => {
      addedLayers.add(layer.id);
    });
    getLayer = vi.fn((id: string) => (addedLayers.has(id) ? {} : undefined));
    removeLayer = vi.fn((id: string) => {
      addedLayers.delete(id);
    });
    setFeatureState = vi.fn();
    remove = vi.fn();
    fitBounds = vi.fn();
    getZoom = vi.fn(() => 10);
    getBounds = vi.fn(() => ({
      toArray: () => [
        [11.4, 47.9],
        [13.0, 49.6],
      ],
    }));
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
    if (path.includes('/units/points')) {
      return Promise.resolve({
        points: [
          {
            mastr_nummer: 'A',
            technology: 'solar',
            category: 'generation',
            capacity_kw: 10,
            storage_capacity_kwh: null,
            latitude: 48.1,
            longitude: 11.5,
          },
        ],
        truncated: false,
      });
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
    addedLayers.clear();
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

  describe('bubble layer cleanup when leaving Kreis level', () => {
    it('removes the unit-points source/layer after navigating back to Land level', async () => {
      // Start already inside a Kreis with a populated (non-empty) points
      // response so the bubble effect actually adds the source/layer.
      useExplorerStore.setState({ selection: { level: 'kreis', landAgs: 'A', kreisAgs: 'X' } });

      renderWithQuery(<MapView />);

      await waitFor(() => {
        expect(addedSources.has('unit-points-source')).toBe(true);
      });
      expect(addedLayers.has('unit-points-circle')).toBe(true);

      // Navigate back to Land level. `useUnitPoints` becomes a disabled
      // query with kreis_ags: '' at this point, so pointsResponse goes back
      // to undefined — this is the exact transition that previously left
      // the old Kreis's bubbles drawn indefinitely over the new view.
      act(() => {
        useExplorerStore.setState({ selection: { level: 'land', landAgs: 'A', kreisAgs: null } });
      });

      await waitFor(() => {
        expect(addedSources.has('unit-points-source')).toBe(false);
      });
      expect(addedLayers.has('unit-points-circle')).toBe(false);
    });
  });
});
