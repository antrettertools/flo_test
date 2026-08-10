import { describe, expect, it } from 'vitest';

import { bubbleRadiusPx } from './bubbleScale';

describe('bubbleRadiusPx', () => {
  it('returns the minimum radius for the smallest capacity', () => {
    expect(bubbleRadiusPx(0, { maxCapacityKw: 100 })).toBe(3);
    expect(bubbleRadiusPx(null, { maxCapacityKw: 100 })).toBe(3);
  });

  it('returns the maximum radius when capacity equals the max', () => {
    expect(bubbleRadiusPx(100, { maxCapacityKw: 100 })).toBeCloseTo(24, 1);
  });

  it('scales by square root, not linearly -- a 4x capacity unit gets 2x the radius', () => {
    const small = bubbleRadiusPx(25, { maxCapacityKw: 100 });
    const large = bubbleRadiusPx(100, { maxCapacityKw: 100 });
    expect(large - 3).toBeCloseTo((small - 3) * 2, 1);
  });

  it('respects custom min/max radius options', () => {
    expect(bubbleRadiusPx(100, { maxCapacityKw: 100, minRadius: 5, maxRadius: 10 })).toBeCloseTo(10, 1);
  });
});
