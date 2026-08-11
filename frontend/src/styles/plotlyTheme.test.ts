import { describe, expect, it } from 'vitest';

import { getPlotlyLayout } from './plotlyTheme';

describe('getPlotlyLayout', () => {
  it('sets the title (and subtitle) via Plotly native layout.title, not a paper-anchored annotation', () => {
    // Regression: an annotation with yref: 'paper' renders inside this
    // project's plot area (not the margin above it) -- see plotlyTheme.ts.
    // layout.title is the only placement that's guaranteed to sit above
    // the plot regardless of plot-area size.
    const layout = getPlotlyLayout('Capacity by technology', 'GW');
    const title = layout.title as { text?: string; font?: { family?: string }; subtitle?: { text?: string } };
    expect(title?.text).toBe('Capacity by technology');
    expect(title?.font?.family).toContain('Jost');
    expect(title?.subtitle?.text).toBe('GW');
  });

  it('sets white backgrounds and hides the x-axis gridlines per c3rro convention', () => {
    const layout = getPlotlyLayout('Title');
    expect(layout.paper_bgcolor).toBe('#ffffff');
    expect(layout.xaxis?.showgrid).toBe(false);
    expect(layout.yaxis?.showgrid).toBe(true);
  });
});
