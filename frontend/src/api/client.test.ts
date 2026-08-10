import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiGet } from './client';

describe('apiGet', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('builds the URL with query params, including repeated array params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiGet('/capacity/totals', { technology: ['solar', 'wind'], region_level: 'land' });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/capacity/totals');
    expect(calledUrl).toContain('technology=solar');
    expect(calledUrl).toContain('technology=wind');
    expect(calledUrl).toContain('region_level=land');
  });

  it('throws when the response is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(apiGet('/meta/health')).rejects.toThrow('500');
  });
});
