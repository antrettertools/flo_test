import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { CapacityAdditionsResponse } from '../api/types';

export interface CapacityAdditionsParams {
  technology?: string[];
  category?: string;
  region_level?: string;
  region_ags?: string[];
  size_class?: string[];
  group_by?: string[];
  date_from?: string;
  date_to?: string;
}

export function useCapacityAdditions(params: CapacityAdditionsParams) {
  return useQuery({
    queryKey: ['capacity-additions', params],
    queryFn: () => apiGet<CapacityAdditionsResponse>('/capacity/additions', params as Record<string, string | string[] | undefined>),
  });
}
