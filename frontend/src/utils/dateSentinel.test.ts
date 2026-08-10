import { describe, expect, it } from 'vitest';

import { excludeSentinelMonths, isPlausibleMonth } from './dateSentinel';

describe('isPlausibleMonth', () => {
  it('rejects the 1900 sentinel and anything before 1950', () => {
    expect(isPlausibleMonth('1900-01')).toBe(false);
    expect(isPlausibleMonth('1949-12')).toBe(false);
  });

  it('accepts 1950 onward', () => {
    expect(isPlausibleMonth('1950-01')).toBe(true);
    expect(isPlausibleMonth('2023-07')).toBe(true);
  });

  it('rejects null', () => {
    expect(isPlausibleMonth(null)).toBe(false);
  });
});

describe('excludeSentinelMonths', () => {
  it('filters out rows with an implausible month, keeps the rest', () => {
    const rows = [{ month: '1900-01', unit_count: 5 }, { month: '2023-07', unit_count: 2 }];
    expect(excludeSentinelMonths(rows)).toEqual([{ month: '2023-07', unit_count: 2 }]);
  });
});
