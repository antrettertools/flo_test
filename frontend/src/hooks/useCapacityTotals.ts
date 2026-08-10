import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { CapacityTotalsResponse } from '../api/types';

export interface CapacityTotalsParams {
  technology?: string[];
  category?: string;
  region_level?: string;
  region_ags?: string[];
  size_class?: string[];
  group_by?: string[];
  as_of_date?: string;
  include_decommissioned?: boolean;
}

export function useCapacityTotals(params: CapacityTotalsParams) {
  return useQuery({
    queryKey: ['capacity-totals', params],
    queryFn: () => apiGet<CapacityTotalsResponse>('/capacity/totals', params as Record<string, string | string[] | undefined>),
  });
}
