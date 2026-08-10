import type { ReactNode } from 'react';

import { colors } from '../../styles/tokens';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'teal';

const VARIANTS: Record<BadgeVariant, { bg: string; text: string }> = {
  default: { bg: colors.greylight, text: colors.text },
  success: { bg: colors.greenlight, text: colors.white },
  warning: { bg: colors.yellow, text: colors.text },
  error: { bg: colors.red, text: colors.white },
  info: { bg: colors.blue, text: colors.white },
  teal: { bg: colors.bluegreen, text: colors.white },
};

export function Badge({ variant = 'default', children }: { variant?: BadgeVariant; children: ReactNode }) {
  const style = VARIANTS[variant];
  return (
    <span
      className="inline-flex items-center font-medium rounded-full px-2.5 py-1.5 text-sm"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {children}
    </span>
  );
}
