import { useCapacityAdditions } from '../hooks/useCapacityAdditions';
import { useCapacityTotals } from '../hooks/useCapacityTotals';
import { useRegions } from '../hooks/useRegions';
import { useExplorerStore } from '../state/explorerStore';
import { excludeSentinelMonths } from '../utils/dateSentinel';
import { Breadcrumb } from './Breadcrumb';
import { FilterPanel } from './FilterPanel';
import { TechnologyChart } from './TechnologyChart';
import { Alert } from './ui/Alert';
import { Card } from './ui/Card';

export function SidePanel() {
  const selection = useExplorerStore((s) => s.selection);
  const filters = useExplorerStore((s) => s.filters);
  const { data: lands } = useRegions('land');
  const { data: kreise } = useRegions('kreis');

  const regionAgs = selection.level === 'kreis' ? selection.kreisAgs! : selection.level === 'land' ? selection.landAgs! : undefined;
  const regionLevel = selection.level === 'kreis' ? 'kreis' : 'land';

  const totalsQuery = useCapacityTotals({
    technology: filters.technologies,
    size_class: filters.sizeClasses.length ? filters.sizeClasses : undefined,
    region_level: regionLevel,
    region_ags: regionAgs ? [regionAgs] : undefined,
    group_by: ['technology'],
    as_of_date: filters.asOfDate,
  });
  const additionsQuery = useCapacityAdditions({
    technology: filters.technologies,
    size_class: filters.sizeClasses.length ? filters.sizeClasses : undefined,
    region_level: regionLevel,
    region_ags: regionAgs ? [regionAgs] : undefined,
    group_by: ['technology', 'month'],
    date_from: filters.dateFrom ?? undefined,
    date_to: filters.dateTo ?? undefined,
  });

  const results =
    filters.timeMode === 'period'
      ? excludeSentinelMonths(additionsQuery.data?.results ?? [])
      : totalsQuery.data?.results ?? [];

  const landName = Array.isArray(lands) ? lands.find((l) => l.ags === selection.landAgs)?.name : undefined;
  const kreisName = Array.isArray(kreise) ? kreise.find((k) => k.ags === selection.kreisAgs)?.name : undefined;

  // Only the query backing the active time mode drives loading/error feedback for
  // the chart — the other one keeps fetching quietly in the background so toggling
  // Total/Period is instant once both have resolved once.
  const activeQuery = filters.timeMode === 'period' ? additionsQuery : totalsQuery;

  return (
    <Card className="pointer-events-auto w-96 max-h-[80vh] overflow-y-auto">
      <div className="space-y-6">
        <Breadcrumb landName={landName} kreisName={kreisName} />
        <FilterPanel />
        <div className="border-t border-c3-greylight pt-4">
          {activeQuery.isError ? (
            <Alert type="error" title="Unable to load chart data">
              {activeQuery.error instanceof Error ? activeQuery.error.message : 'Please try again.'}
            </Alert>
          ) : activeQuery.isLoading ? (
            <p data-testid="technology-chart-loading" className="animate-pulse text-sm text-c3-greydark">
              Loading chart…
            </p>
          ) : (
            <TechnologyChart results={results} metric={filters.metric} />
          )}
        </div>
      </div>
    </Card>
  );
}
