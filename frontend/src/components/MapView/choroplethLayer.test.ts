import { describe, expect, it } from 'vitest';

import { buildChoroplethColorExpression } from './choroplethLayer';

describe('buildChoroplethColorExpression', () => {
  it('builds a feature-state-driven interpolate expression bounded by the max value', () => {
    const expr = buildChoroplethColorExpression(100);
    expect(expr[0]).toBe('case');
    expect(JSON.stringify(expr)).toContain('#93d2e1'); // bluelight, low end
    expect(JSON.stringify(expr)).toContain('#407188'); // bluedark, high end
  });

  it('falls back to a neutral color for regions with no data (feature-state value undefined)', () => {
    const expr = buildChoroplethColorExpression(100);
    // 'case' structure: ['case', <value === null condition>, <no-data color>, <default: interpolate>]
    // the color used when the no-data condition matches is at index 2.
    const fallback = expr[2];
    expect(fallback).toBe('#d9d8cd'); // greylight, matches c3rro's neutral/no-data convention
  });
});
