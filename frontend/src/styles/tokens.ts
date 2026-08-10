// kept in sync with tailwind.config.js theme.extend.colors.c3
// (Tailwind config is plain JS/CommonJS and can't import this TS module
// without adding new tooling, so the 17 hex values are duplicated there.)
export const colors = {
  text: '#33302F',
  greydark: '#5e5a58',
  grey: '#bdb2aa',
  greylight: '#d9d8cd',
  white: '#ffffff',
  bluegreen: '#4ab79f',
  blue: '#4597bf',
  bluedark: '#407188',
  bluelight: '#93d2e1',
  green: '#3e7263',
  greendark: '#205959',
  greenlight: '#89a767',
  red: '#c04343',
  orange: '#e18e2a',
  yellow: '#f8c36e',
  yellowgreen: '#b1b52e',
  yellowlight: '#fef4dc',
} as const;

export type ColorName = keyof typeof colors;

// Deliberately NOT using `main` (opens on bluegreen) for data encoding --
// bluegreen is reserved for interactive/selected state across the app.
// See docs/superpowers/specs/2026-08-10-phase4-dashboard-ui-design.md Section 5.
export const palettes = {
  blues: [colors.bluelight, colors.bluedark],
  mixed: [
    colors.bluedark,
    colors.blue,
    colors.bluegreen,
    colors.green,
    colors.yellowgreen,
    colors.yellow,
    colors.orange,
    colors.red,
  ],
} as const;

export const spacing = {
  xs: '0.25rem',
  sm: '0.5rem',
  md: '1rem',
  lg: '1.5rem',
  xl: '2rem',
} as const;

// Numeric font sizes for Plotly layout config, which takes raw numbers
// rather than CSS classes. Component CSS font sizing should use Tailwind's
// built-in type scale (text-xs/text-sm/etc.) instead of these.
export const fontSize = {
  title: 16,
  subtitle: 12,
  axisTick: 12,
  legend: 11,
} as const;
