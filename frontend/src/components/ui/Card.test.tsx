import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Card } from './Card';

describe('Card', () => {
  it('renders title, subtitle, and children', () => {
    render(
      <Card title="Technologies" subtitle="by capacity">
        <p>content</p>
      </Card>
    );
    expect(screen.getByText('Technologies')).toBeInTheDocument();
    expect(screen.getByText('by capacity')).toBeInTheDocument();
    expect(screen.getByText('content')).toBeInTheDocument();
  });

  it('omits the header block when no title or subtitle given', () => {
    render(<Card><p>content only</p></Card>);
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });
});
