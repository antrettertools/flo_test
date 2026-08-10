import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { CapacityGroupResult } from '../api/types';
import { TechnologyChart } from './TechnologyChart';

const results: CapacityGroupResult[] = [
  { category: 'generation', technology: 'solar', region_ags: null, size_class: null, month: null, unit_count: 6236704, capacity_kw_sum: 113086749.89, storage_capacity_kwh_sum: null },
  { category: 'generation', technology: 'wind', region_ags: null, size_class: null, month: null, unit_count: 32224, capacity_kw_sum: 81351967.017, storage_capacity_kwh_sum: null },
];

describe('TechnologyChart', () => {
  it('renders one bar per technology when metric is capacity', () => {
    render(<TechnologyChart results={results} metric="capacity" />);
    expect(screen.getByTestId('technology-chart')).toBeInTheDocument();
  });

  it('renders unit_count values when metric is count', () => {
    render(<TechnologyChart results={results} metric="count" />);
    expect(screen.getByTestId('technology-chart')).toBeInTheDocument();
  });

  it('renders an empty-state message when there are no results', () => {
    render(<TechnologyChart results={[]} metric="capacity" />);
    expect(screen.getByText(/no data for the current filters/i)).toBeInTheDocument();
  });
});
