import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

import type { CapacityGroupResult } from '../api/types';
import { getPlotlyLayout } from '../styles/plotlyTheme';
import { palettes } from '../styles/tokens';

// The project depends on plotly.js-dist-min (not the full plotly.js) to keep
// the bundle small, so the default `react-plotly.js` import (which requires
// the full plotly.js peer dependency) can't be used. The documented
// react-plotly.js/factory entry point builds the component from any Plotly
// instance instead.
const Plot = createPlotlyComponent(Plotly);

interface TechnologyChartProps {
  results: CapacityGroupResult[];
  metric: 'count' | 'capacity';
}

export function TechnologyChart({ results, metric }: TechnologyChartProps) {
  if (results.length === 0) {
    return <p className="text-sm text-c3-greydark">No data for the current filters.</p>;
  }

  const byTechnology = new Map<string, number>();
  results.forEach((row) => {
    if (!row.technology) return;
    const value = metric === 'capacity' ? row.capacity_kw_sum ?? row.storage_capacity_kwh_sum ?? 0 : row.unit_count;
    byTechnology.set(row.technology, (byTechnology.get(row.technology) ?? 0) + value);
  });

  const technologies = Array.from(byTechnology.keys());
  const values = technologies.map((t) => byTechnology.get(t)!);

  return (
    <div data-testid="technology-chart">
      <Plot
        data={[
          {
            type: 'bar',
            x: values,
            y: technologies,
            orientation: 'h',
            marker: { color: palettes.mixed.slice(0, technologies.length) },
          },
        ]}
        layout={getPlotlyLayout(metric === 'capacity' ? 'Capacity by technology' : 'Unit count by technology')}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%', height: '300px' }}
      />
    </div>
  );
}
