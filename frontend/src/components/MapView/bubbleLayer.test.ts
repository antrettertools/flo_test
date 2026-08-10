import { describe, expect, it } from 'vitest';

import { clusterPoints } from './bubbleLayer';
import type { UnitPoint } from '../../api/types';

function point(overrides: Partial<UnitPoint>): UnitPoint {
  return {
    mastr_nummer: 'X',
    technology: 'solar',
    category: 'generation',
    capacity_kw: 10,
    storage_capacity_kwh: null,
    latitude: 48.13,
    longitude: 11.58,
    ...overrides,
  };
}

describe('clusterPoints', () => {
  it('returns one feature per point when zoomed in enough to separate them', () => {
    const points = [
      point({ mastr_nummer: 'A', latitude: 48.1, longitude: 11.5 }),
      point({ mastr_nummer: 'B', latitude: 49.5, longitude: 12.9 }),
    ];
    const result = clusterPoints(points, { zoom: 18, bounds: [11.4, 47.9, 13.0, 49.6] });
    expect(result.features).toHaveLength(2);
    expect(result.features.every((f) => f.properties?.cluster !== true)).toBe(true);
  });

  it('clusters nearby points at low zoom and sums their capacity', () => {
    const points = [
      point({ mastr_nummer: 'A', capacity_kw: 10, latitude: 48.135, longitude: 11.582 }),
      point({ mastr_nummer: 'B', capacity_kw: 20, latitude: 48.136, longitude: 11.583 }),
    ];
    const result = clusterPoints(points, { zoom: 0, bounds: [-180, -85, 180, 85] });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties?.cluster).toBe(true);
    expect(result.features[0].properties?.capacityKwSum).toBe(30);
  });

  it('carries capacityKw through on individual (non-clustered) points', () => {
    const points = [point({ mastr_nummer: 'A', capacity_kw: 42 })];
    const result = clusterPoints(points, { zoom: 18, bounds: [11.4, 47.9, 13.0, 49.6] });
    expect(result.features[0].properties?.capacityKwSum).toBe(42);
  });
});
