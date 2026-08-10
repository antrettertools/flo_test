import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { RegionOut } from '../api/types';

export function useRegions(level?: 'land' | 'kreis') {
  return useQuery({
    queryKey: ['regions', level],
    queryFn: () => apiGet<RegionOut[]>('/regions', level ? { level } : undefined),
  });
}
