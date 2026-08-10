const SENTINEL_CUTOFF_MONTH = '1950-01';

export function isPlausibleMonth(month: string | null): boolean {
  if (!month) return false;
  return month >= SENTINEL_CUTOFF_MONTH;
}

export function excludeSentinelMonths<T extends { month: string | null }>(rows: T[]): T[] {
  return rows.filter((row) => isPlausibleMonth(row.month));
}
