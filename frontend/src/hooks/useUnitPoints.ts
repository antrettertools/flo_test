import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { UnitPointsResponse } from '../api/types';

export interface UnitPointsParams {
  kreis_ags: string;
  technology?: string[];
  category?: string;
  size_class?: string[];
}

export function useUnitPoints(params: UnitPointsParams) {
  return useQuery({
    queryKey: ['unit-points', params],
    queryFn: () => apiGet<UnitPointsResponse>('/units/points', params as Record<string, string | string[] | undefined>),
    enabled: Boolean(params.kreis_ags),
  });
}
