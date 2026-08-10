import { describe, expect, it } from 'vitest';

import { getPlotlyLayout } from './plotlyTheme';

describe('getPlotlyLayout', () => {
  it('sets the title annotation with the correct text and font', () => {
    const layout = getPlotlyLayout('Capacity by technology', 'GW');
    const titleAnnotation = layout.annotations?.find((a) => a.text === 'Capacity by technology');
    expect(titleAnnotation).toBeDefined();
    expect(titleAnnotation?.font?.family).toContain('Jost');
  });

  it('sets white backgrounds and hides the x-axis gridlines per c3rro convention', () => {
    const layout = getPlotlyLayout('Title');
    expect(layout.paper_bgcolor).toBe('#ffffff');
    expect(layout.xaxis?.showgrid).toBe(false);
    expect(layout.yaxis?.showgrid).toBe(true);
  });
});
