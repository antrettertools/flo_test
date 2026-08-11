import * as maplibregl from 'maplibre-gl';
import { useEffect, useRef } from 'react';

import { useCapacityTotals } from '../../hooks/useCapacityTotals';
import { useRegionGeojson } from '../../hooks/useRegionGeojson';
import { useUnitPoints } from '../../hooks/useUnitPoints';
import { useExplorerStore } from '../../state/explorerStore';
import { colors } from '../../styles/tokens';
import { bubbleRadiusPx } from '../../utils/bubbleScale';
import { Alert } from '../ui/Alert';
import { clusterPoints } from './bubbleLayer';
import { buildChoroplethColorExpression } from './choroplethLayer';

const BLANK_STYLE = {
  version: 8 as const,
  sources: {},
  layers: [{ id: 'background', type: 'background' as const, paint: { 'background-color': colors.yellowlight } }],
};

export function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const selection = useExplorerStore((s) => s.selection);
  const filters = useExplorerStore((s) => s.filters);
  const selectLand = useExplorerStore((s) => s.selectLand);
  const selectKreis = useExplorerStore((s) => s.selectKreis);

  const activeLevel = selection.level === 'national' ? 'land' : 'kreis';
  const { data: geojson } = useRegionGeojson(activeLevel);
  const { data: totals } = useCapacityTotals({
    technology: filters.technologies,
    region_level: activeLevel,
    group_by: ['region'],
    as_of_date: filters.asOfDate,
  });
  const { data: pointsResponse } = useUnitPoints({
    kreis_ags: selection.kreisAgs ?? '',
    technology: filters.technologies,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: BLANK_STYLE,
      center: [10.4515, 51.1657],
      zoom: 5,
    });
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;

    // Only one of land-fill/kreis-fill should ever be on the map at once.
    // Task 12 solved this exact problem for the bubble layer (see the
    // cleanup effect below) but the choropleth effect never got the mirror
    // fix: without this, drilling into a Land leaves kreis-fill stacked on
    // top of land-fill, and navigating back via the breadcrumb leaves the
    // Kreis choropleth visible (and both layers' click handlers live,
    // which could fire together and skip two levels in one click).
    const inactiveLevel = activeLevel === 'land' ? 'kreis' : 'land';
    const inactiveSourceId = `${inactiveLevel}-source`;
    const inactiveLayerId = `${inactiveLevel}-fill`;
    if (map.getLayer(inactiveLayerId)) map.removeLayer(inactiveLayerId);
    if (map.getSource(inactiveSourceId)) map.removeSource(inactiveSourceId);

    const sourceId = `${activeLevel}-source`;
    const layerId = `${activeLevel}-fill`;

    // Hoisted out of the add-guard below (and using the same metric branch
    // as the setFeatureState call further down) so the ramp domain
    // recomputes whenever totals or the active metric change, rather than
    // being frozen at whatever `totals` happened to be (often still
    // undefined) the first time this source was added.
    const maxValue = Math.max(
      ...(totals?.results.map((r) => (filters.metric === 'capacity' ? r.capacity_kw_sum : r.unit_count) ?? 0) ?? [1]),
      1,
    );

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, { type: 'geojson', data: geojson, promoteId: 'ags' });
      map.addLayer({
        id: layerId,
        type: 'fill',
        source: sourceId,
        paint: { 'fill-color': buildChoroplethColorExpression(maxValue), 'fill-outline-color': colors.greydark },
      });
      map.on('click', layerId, (e: maplibregl.MapLayerMouseEvent) => {
        const ags = e.features?.[0]?.properties?.ags as string | undefined;
        if (!ags) return;
        if (activeLevel === 'land') {
          selectLand(ags);
        } else {
          // Read landAgs from the store at click time, not from this closure's
          // render-time `selection`: the click listener is registered once per
          // sourceId (see the `!map.getSource(sourceId)` guard above) and is
          // never re-bound afterward, so a value captured here would go stale
          // the moment the user picks a different Land later.
          const currentLandAgs = useExplorerStore.getState().selection.landAgs;
          if (currentLandAgs) selectKreis(currentLandAgs, ags);
        }
      });
    } else {
      map.setPaintProperty(layerId, 'fill-color', buildChoroplethColorExpression(maxValue));
    }

    totals?.results.forEach((row) => {
      if (!row.region_ags) return;
      const value = filters.metric === 'capacity' ? row.capacity_kw_sum : row.unit_count;
      map.setFeatureState({ source: sourceId, id: row.region_ags }, { value: value ?? 0 });
    });
  }, [geojson, totals, activeLevel, filters.metric, selection.landAgs, selectLand, selectKreis]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const sourceId = 'unit-points-source';
    const layerId = 'unit-points-circle';

    if (!pointsResponse || selection.level !== 'kreis') {
      // Leaving Kreis level (or no data loaded yet) — actively clear any
      // bubbles left over from a previously selected Kreis. `useUnitPoints`
      // becomes a disabled query with no data once kreis_ags is empty, so
      // without this the old Kreis's bubbles would stay drawn indefinitely
      // over the new Land/national view.
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      return;
    }

    const clustered = clusterPoints(pointsResponse.points, {
      zoom: map.getZoom(),
      bounds: map.getBounds().toArray().flat() as [number, number, number, number],
    });
    const maxCapacity = Math.max(...pointsResponse.points.map((p) => p.capacity_kw ?? p.storage_capacity_kwh ?? 0), 1);

    const geojsonWithRadius = {
      ...clustered,
      features: clustered.features.map((f) => ({
        ...f,
        properties: {
          ...f.properties,
          radiusPx: bubbleRadiusPx(f.properties.capacityKwSum, { maxCapacityKw: maxCapacity }),
        },
      })),
    };

    if (map.getSource(sourceId)) {
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojsonWithRadius as GeoJSON.FeatureCollection);
    } else {
      map.addSource(sourceId, { type: 'geojson', data: geojsonWithRadius as GeoJSON.FeatureCollection });
      map.addLayer({
        id: layerId,
        type: 'circle',
        source: sourceId,
        paint: {
          'circle-radius': ['get', 'radiusPx'],
          'circle-color': colors.bluegreen,
          'circle-opacity': 0.7,
          'circle-stroke-color': colors.white,
          'circle-stroke-width': 1,
        },
      });
    }
  }, [pointsResponse, selection.level]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} data-testid="map-container" className="h-full w-full" />
      {pointsResponse?.truncated && (
        <div className="absolute bottom-4 left-4 max-w-xs shadow-md">
          <Alert type="warning">Showing a partial view — zoom in further to see all units.</Alert>
        </div>
      )}
    </div>
  );
}
