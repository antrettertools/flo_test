import type { Layout } from 'plotly.js';

import { colors, fontSize } from './tokens';

export function getPlotlyLayout(
  title = '',
  subtitle = '',
  options: Partial<Layout> = {}
): Partial<Layout> {
  const annotations: Partial<Layout>['annotations'] = [];

  if (title) {
    annotations.push({
      text: title,
      xref: 'paper',
      yref: 'paper',
      x: 0.08,
      y: 0.98,
      xanchor: 'left',
      yanchor: 'top',
      showarrow: false,
      font: { family: '"Jost", "Lato", Arial, sans-serif', size: fontSize.title, color: colors.text },
    });
  }

  if (subtitle) {
    annotations.push({
      text: subtitle,
      xref: 'paper',
      yref: 'paper',
      x: 0.08,
      y: 0.93,
      xanchor: 'left',
      yanchor: 'top',
      showarrow: false,
      font: { family: '"Lato", Arial, sans-serif', size: fontSize.subtitle, color: colors.bluegreen },
    });
  }

  return {
    paper_bgcolor: colors.white,
    plot_bgcolor: colors.white,
    annotations,
    font: { family: '"Lato", Arial, sans-serif', size: fontSize.axisTick, color: colors.text },
    xaxis: {
      showline: true,
      linewidth: 1,
      linecolor: colors.greydark,
      showgrid: false,
      zeroline: false,
      tickcolor: colors.greydark,
      tickfont: { size: fontSize.axisTick, color: colors.text },
    },
    yaxis: {
      showline: false,
      zeroline: false,
      showgrid: true,
      gridwidth: 0.5,
      gridcolor: colors.grey,
      tickcolor: colors.greydark,
      tickfont: { size: fontSize.axisTick, color: colors.text },
    },
    legend: {
      bgcolor: 'rgba(255, 255, 255, 1)',
      bordercolor: colors.greydark,
      borderwidth: 1,
      font: { size: fontSize.legend, color: colors.text },
      x: 1.02,
      y: 1,
      xanchor: 'left',
      yanchor: 'top',
    },
    margin: { l: 80, r: 40, t: 100, b: 60 },
    hovermode: 'x unified',
    ...options,
  };
}
