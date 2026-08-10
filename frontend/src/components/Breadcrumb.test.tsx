import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import { useExplorerStore } from '../state/explorerStore';
import { Breadcrumb } from './Breadcrumb';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

describe('Breadcrumb', () => {
  it('shows only "Germany" at national level', () => {
    render(<Breadcrumb />);
    expect(screen.getByText('Germany')).toBeInTheDocument();
    expect(screen.queryByText('>')).not.toBeInTheDocument();
  });

  it('shows Germany > Land name when a Land is selected', () => {
    useExplorerStore.setState((s) => ({ ...s, selection: { level: 'land', landAgs: '09', kreisAgs: null } }));
    render(<Breadcrumb landName="Bayern" />);
    expect(screen.getByText('Bayern')).toBeInTheDocument();
  });

  it('clicking "Germany" calls selectNational', async () => {
    useExplorerStore.setState((s) => ({ ...s, selection: { level: 'land', landAgs: '09', kreisAgs: null } }));
    render(<Breadcrumb landName="Bayern" />);
    await userEvent.click(screen.getByText('Germany'));
    expect(useExplorerStore.getState().selection.level).toBe('national');
  });
});
