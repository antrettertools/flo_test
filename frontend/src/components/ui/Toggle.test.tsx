import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('calls onChange with the flipped value when clicked', async () => {
    const onChange = vi.fn();
    render(<Toggle enabled={false} onChange={onChange} label="Include storage" />);
    await userEvent.click(screen.getByRole('button'));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('renders the label', () => {
    render(<Toggle enabled onChange={() => {}} label="Include storage" />);
    expect(screen.getByText('Include storage')).toBeInTheDocument();
  });
});
