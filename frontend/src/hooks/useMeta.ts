import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { HealthResponse, SizeClassMeta, TechnologyMeta } from '../api/types';

export function useHealth() {
  return useQuery({ queryKey: ['meta-health'], queryFn: () => apiGet<HealthResponse>('/meta/health') });
}

export function useTechnologies() {
  return useQuery({
    queryKey: ['meta-technologies'],
    queryFn: () => apiGet<TechnologyMeta[]>('/meta/technologies'),
    staleTime: Infinity,
  });
}

export function useSizeClasses() {
  return useQuery({
    queryKey: ['meta-size-classes'],
    queryFn: () => apiGet<SizeClassMeta[]>('/meta/size-classes'),
    staleTime: Infinity,
  });
}
