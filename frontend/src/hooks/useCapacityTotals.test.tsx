import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import { useCapacityTotals } from './useCapacityTotals';

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe('useCapacityTotals', () => {
  afterEach(() => vi.restoreAllMocks());

  it('fetches /capacity/totals with the given filters', async () => {
    const apiGetSpy = vi.spyOn(client, 'apiGet').mockResolvedValue({
      as_of_date: '2026-08-10',
      include_decommissioned: false,
      group_by: ['technology'],
      results: [],
    });

    const { result } = renderHook(
      () => useCapacityTotals({ technology: ['solar'], group_by: ['technology'] }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGetSpy).toHaveBeenCalledWith(
      '/capacity/totals',
      expect.objectContaining({ technology: ['solar'], group_by: ['technology'] })
    );
  });
});
