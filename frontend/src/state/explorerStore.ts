import { create } from 'zustand';

export type Tab = 'generation' | 'storage';
export type Metric = 'count' | 'capacity';
export type TimeMode = 'total' | 'period';
export type RegionLevel = 'national' | 'land' | 'kreis';

export const DEFAULT_RENEWABLE_TECHNOLOGIES = ['solar', 'wind', 'biomass', 'hydro', 'gsgk'];

interface Selection {
  level: RegionLevel;
  landAgs: string | null;
  kreisAgs: string | null;
}

interface Filters {
  technologies: string[];
  sizeClasses: string[];
  metric: Metric;
  timeMode: TimeMode;
  asOfDate: string;
  dateFrom: string | null;
  dateTo: string | null;
}

interface ExplorerState {
  tab: Tab;
  selection: Selection;
  filters: Filters;
  setTab: (tab: Tab) => void;
  selectNational: () => void;
  selectLand: (landAgs: string) => void;
  selectKreis: (landAgs: string, kreisAgs: string) => void;
  setMetric: (metric: Metric) => void;
  setTimeMode: (timeMode: TimeMode) => void;
  setTechnologies: (technologies: string[]) => void;
  setSizeClasses: (sizeClasses: string[]) => void;
  setDateRange: (dateFrom: string | null, dateTo: string | null) => void;
}

function initialState() {
  return {
    tab: 'generation' as Tab,
    selection: { level: 'national', landAgs: null, kreisAgs: null } as Selection,
    filters: {
      technologies: [...DEFAULT_RENEWABLE_TECHNOLOGIES],
      sizeClasses: [] as string[],
      metric: 'capacity' as Metric,
      timeMode: 'total' as TimeMode,
      asOfDate: new Date().toISOString().slice(0, 10),
      dateFrom: null,
      dateTo: null,
    } as Filters,
  };
}

export const useExplorerStore = create<ExplorerState>()((set) => ({
  ...initialState(),
  setTab: (tab) =>
    set((state) => ({
      tab,
      filters: {
        ...state.filters,
        technologies: tab === 'storage' ? ['storage'] : [...DEFAULT_RENEWABLE_TECHNOLOGIES],
        sizeClasses: [],
        // Storage has no capacity metric to show (capacity_kw_sum is only
        // populated for generation-category units server-side) — the spec
        // gives storage unit count only, no capacity/energy toggle. Force
        // count mode on entry so the tab never lands on a metric that's
        // structurally guaranteed to render as zero.
        metric: tab === 'storage' ? 'count' : state.filters.metric,
      },
    })),
  selectNational: () => set({ selection: { level: 'national', landAgs: null, kreisAgs: null } }),
  selectLand: (landAgs) => set({ selection: { level: 'land', landAgs, kreisAgs: null } }),
  selectKreis: (landAgs, kreisAgs) => set({ selection: { level: 'kreis', landAgs, kreisAgs } }),
  setMetric: (metric) => set((state) => ({ filters: { ...state.filters, metric } })),
  setTimeMode: (timeMode) => set((state) => ({ filters: { ...state.filters, timeMode } })),
  setTechnologies: (technologies) => set((state) => ({ filters: { ...state.filters, technologies } })),
  setSizeClasses: (sizeClasses) => set((state) => ({ filters: { ...state.filters, sizeClasses } })),
  setDateRange: (dateFrom, dateTo) => set((state) => ({ filters: { ...state.filters, dateFrom, dateTo } })),
  getInitialState: initialState,
}));
