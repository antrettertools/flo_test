import type { ExpressionSpecification } from 'maplibre-gl';

import { colors, palettes } from '../../styles/tokens';

export function buildChoroplethColorExpression(maxValue: number): ExpressionSpecification {
  const [low, high] = palettes.blues;
  return [
    'case',
    ['==', ['feature-state', 'value'], null],
    colors.greylight,
    [
      'interpolate',
      ['linear'],
      ['feature-state', 'value'],
      0,
      low,
      maxValue,
      high,
    ],
  ] as unknown as ExpressionSpecification;
}
