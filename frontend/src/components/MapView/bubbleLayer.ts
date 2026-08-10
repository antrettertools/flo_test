import Supercluster from 'supercluster';

import type { UnitPoint } from '../../api/types';

interface ClusterProps {
  mastr_nummer?: string;
  capacityKwSum: number;
  // supercluster only attaches `cluster: true` to synthesized cluster
  // features; individual (non-clustered) points never get this property at
  // all, so it must be optional rather than a plain boolean.
  cluster?: true;
}

export function clusterPoints(
  points: UnitPoint[],
  opts: { zoom: number; bounds: [number, number, number, number] }
): GeoJSON.FeatureCollection<GeoJSON.Point, ClusterProps> {
  const index = new Supercluster<{ capacityKwSum: number }, { capacityKwSum: number }>({
    radius: 40,
    maxZoom: 20,
    map: (props) => ({ capacityKwSum: props.capacityKwSum }),
    reduce: (accumulated, props) => {
      accumulated.capacityKwSum += props.capacityKwSum;
    },
  });

  index.load(
    points.map((p) => ({
      type: 'Feature',
      properties: { mastr_nummer: p.mastr_nummer, capacityKwSum: p.capacity_kw ?? p.storage_capacity_kwh ?? 0 },
      geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
    }))
  );

  // supercluster's getClusters returns a plain array of Features, not a
  // FeatureCollection — wrap it so callers get a standard GeoJSON object
  // (MapLibre's GeoJSONSource.setData and the test suite both expect
  // `.features`, not a bare array).
  const features = index.getClusters(opts.bounds, Math.round(opts.zoom));
  return {
    type: 'FeatureCollection',
    features: features as GeoJSON.Feature<GeoJSON.Point, ClusterProps>[],
  };
}
