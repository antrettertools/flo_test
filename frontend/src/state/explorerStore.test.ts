import { beforeEach, describe, expect, it } from 'vitest';

import { useExplorerStore } from './explorerStore';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

describe('explorerStore', () => {
  it('starts at national level on the generation tab with default renewable technologies', () => {
    const state = useExplorerStore.getState();
    expect(state.tab).toBe('generation');
    expect(state.selection).toEqual({ level: 'national', landAgs: null, kreisAgs: null });
    expect(state.filters.technologies).toEqual(['solar', 'wind', 'biomass', 'hydro', 'gsgk']);
  });

  it('selectLand sets level to land and clears kreisAgs', () => {
    useExplorerStore.getState().selectKreis('09', '09162');
    useExplorerStore.getState().selectLand('11');
    const state = useExplorerStore.getState();
    expect(state.selection).toEqual({ level: 'land', landAgs: '11', kreisAgs: null });
  });

  it('selectKreis sets level to kreis with both codes', () => {
    useExplorerStore.getState().selectKreis('09', '09162');
    expect(useExplorerStore.getState().selection).toEqual({ level: 'kreis', landAgs: '09', kreisAgs: '09162' });
  });

  it('selectNational resets the selection entirely', () => {
    useExplorerStore.getState().selectKreis('09', '09162');
    useExplorerStore.getState().selectNational();
    expect(useExplorerStore.getState().selection).toEqual({ level: 'national', landAgs: null, kreisAgs: null });
  });

  it('setTab to storage fixes technologies to ["storage"] and clears size classes', () => {
    useExplorerStore.getState().setSizeClasses(['<5 kWh']);
    useExplorerStore.getState().setTab('storage');
    const state = useExplorerStore.getState();
    expect(state.tab).toBe('storage');
    expect(state.filters.technologies).toEqual(['storage']);
    expect(state.filters.sizeClasses).toEqual([]);
  });

  it('setTab back to generation restores the default renewable technology set', () => {
    useExplorerStore.getState().setTab('storage');
    useExplorerStore.getState().setTab('generation');
    expect(useExplorerStore.getState().filters.technologies).toEqual([
      'solar', 'wind', 'biomass', 'hydro', 'gsgk',
    ]);
  });

  it('setTab to storage forces metric to count (capacity_kw_sum is always null for storage)', () => {
    useExplorerStore.getState().setMetric('capacity');
    useExplorerStore.getState().setTab('storage');
    expect(useExplorerStore.getState().filters.metric).toBe('count');
  });
});
