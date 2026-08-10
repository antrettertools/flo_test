import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';

export function useRegionGeojson(level: 'land' | 'kreis') {
  return useQuery({
    queryKey: ['region-geojson', level],
    queryFn: () => apiGet<GeoJSON.FeatureCollection>(`/regions/${level}/geojson`),
    staleTime: Infinity,
  });
}
