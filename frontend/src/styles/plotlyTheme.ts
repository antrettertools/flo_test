import type { Layout } from 'plotly.js';

import { colors, fontSize } from './tokens';

export function getPlotlyLayout(
  title = '',
  subtitle = '',
  options: Partial<Layout> = {}
): Partial<Layout> {
  // Plotly's own `layout.title` (not a hand-rolled `paper`-anchored
  // annotation) is what correctly reserves and renders inside the margin
  // above the plot area -- annotation `yref: 'paper'` coordinates here are
  // scoped to the plot/axes box itself, not the full figure including
  // margins, so a title placed that way lands inside the plot instead of
  // above it (verified against this project's bundled plotly.js-dist-min).
  const titleLayout = title
    ? {
        text: title,
        x: 0.08,
        xanchor: 'left' as const,
        font: { family: '"Jost", "Lato", Arial, sans-serif', size: fontSize.title, color: colors.text },
        ...(subtitle
          ? {
              subtitle: {
                text: subtitle,
                font: { family: '"Lato", Arial, sans-serif', size: fontSize.subtitle, color: colors.bluegreen },
              },
            }
          : {}),
      }
    : undefined;

  return {
    title: titleLayout,
    paper_bgcolor: colors.white,
    plot_bgcolor: colors.white,
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
